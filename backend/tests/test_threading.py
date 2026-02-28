"""Tests for the JWZ threading engine.

Tests are organized into two groups:
1. Pure algorithm tests — use in-memory Message-like objects, no DB mocking.
2. DB integration tests — mock AsyncSession to verify persistence logic.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import (
    Message,
    MessageProcessingStatus,
    ThreadMessage,
)
from app.services.threading import (
    Container,
    _build_id_table,
    _build_references,
    _find_root_set,
    _group_by_subject,
    _prune_empty,
    normalize_subject,
    thread_messages,
)

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Helpers: lightweight message factory
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)


def _make_message(
    *,
    message_id_header: str,
    subject: str = "Test Subject",
    sender_email: str = "alice@example.com",
    sender_name: str | None = "Alice",
    date: datetime = _NOW,
    in_reply_to: str | None = None,
    references_header: list[str] | None = None,
    group_id: uuid.UUID | None = None,
    processing_status: MessageProcessingStatus = MessageProcessingStatus.pending,
) -> Message:
    """Create a Message ORM instance with minimal fields set for threading.

    Uses the proper SQLAlchemy constructor so instrumentation is initialized.
    """
    return Message(
        id=uuid.uuid4(),
        group_id=group_id or uuid.uuid4(),
        gmail_id=f"gmail-{uuid.uuid4().hex[:8]}",
        message_id_header=message_id_header,
        in_reply_to=in_reply_to,
        references_header=references_header,
        subject=subject,
        sender_email=sender_email,
        sender_name=sender_name,
        date=date,
        body_text=None,
        body_html=None,
        raw_headers=None,
        has_attachments=False,
        processing_status=processing_status,
        recipients=None,
    )


# ===========================================================================
# 1. normalize_subject()
# ===========================================================================


class TestNormalizeSubject:
    """Test subject line normalization for thread grouping."""

    def test_strip_re_prefix(self) -> None:
        assert normalize_subject("Re: Hello") == "hello"

    def test_strip_re_prefix_case_insensitive(self) -> None:
        assert normalize_subject("RE: Hello") == "hello"

    def test_strip_fwd_prefix(self) -> None:
        assert normalize_subject("Fwd: Hello") == "hello"

    def test_strip_fw_prefix(self) -> None:
        assert normalize_subject("FW: Hello") == "hello"

    def test_strip_list_tag(self) -> None:
        assert normalize_subject("[dev-list] Hello") == "hello"

    def test_strip_multiple_prefixes(self) -> None:
        assert normalize_subject("Re: Re: Fwd: [list] Hello") == "hello"

    def test_strip_whitespace(self) -> None:
        assert normalize_subject("   Re:  Hello   ") == "hello"

    def test_empty_subject(self) -> None:
        assert normalize_subject("") == ""

    def test_only_prefix(self) -> None:
        assert normalize_subject("Re:") == ""

    def test_nested_brackets(self) -> None:
        assert normalize_subject("[dev] [urgent] Topic") == "topic"

    def test_preserves_meaningful_content(self) -> None:
        assert normalize_subject("Project Update") == "project update"

    def test_re_colon_no_space(self) -> None:
        assert normalize_subject("Re:Hello") == "hello"

    def test_fwd_colon_no_space(self) -> None:
        assert normalize_subject("Fwd:Hello") == "hello"


# ===========================================================================
# 2. _build_id_table()  (Phase 1)
# ===========================================================================


class TestBuildIdTable:
    """Phase 1: Building the container table from messages."""

    def test_single_message(self) -> None:
        msg = _make_message(message_id_header="<a@ex>")
        table = _build_id_table([msg])
        assert "<a@ex>" in table
        assert table["<a@ex>"].message is msg
        assert table["<a@ex>"].is_ghost is False

    def test_multiple_messages(self) -> None:
        msgs = [
            _make_message(message_id_header="<a@ex>"),
            _make_message(message_id_header="<b@ex>"),
        ]
        table = _build_id_table(msgs)
        assert len(table) == 2
        assert table["<a@ex>"].message is msgs[0]
        assert table["<b@ex>"].message is msgs[1]

    def test_duplicate_message_id_uses_first(self) -> None:
        """If two messages share the same Message-ID, keep the first one."""
        msg1 = _make_message(message_id_header="<a@ex>", subject="First")
        msg2 = _make_message(message_id_header="<a@ex>", subject="Second")
        table = _build_id_table([msg1, msg2])
        assert len(table) == 1
        assert table["<a@ex>"].message is msg1

    def test_ghost_container_filled_when_message_arrives(self) -> None:
        """Ghost container pre-created via references is filled when message arrives."""
        msg_a = _make_message(
            message_id_header="<a@ex>",
            references_header=["<ghost@ex>"],
        )
        msg_ghost = _make_message(message_id_header="<ghost@ex>")
        # msg_a references <ghost@ex> -> ghost container created in first pass
        # msg_ghost has message_id_header="<ghost@ex>" -> fills the ghost in second pass
        table = _build_id_table([msg_a, msg_ghost])
        assert table["<ghost@ex>"].message is msg_ghost
        assert table["<ghost@ex>"].is_ghost is False

    def test_in_reply_to_ghost_created_in_first_pass(self) -> None:
        """In-Reply-To reference also creates ghost in first pass."""
        msg = _make_message(
            message_id_header="<child@ex>",
            in_reply_to="<parent@ex>",
        )
        table = _build_id_table([msg])
        assert "<parent@ex>" in table
        assert table["<parent@ex>"].is_ghost is True
        assert table["<parent@ex>"].message is None

    def test_empty_list_returns_empty_table(self) -> None:
        table = _build_id_table([])
        assert table == {}


# ===========================================================================
# 3. _build_references()  (Phase 2)
# ===========================================================================


class TestBuildReferences:
    """Phase 2: Linking containers via References + In-Reply-To."""

    def test_simple_in_reply_to(self) -> None:
        parent = _make_message(message_id_header="<parent@ex>")
        child = _make_message(message_id_header="<child@ex>", in_reply_to="<parent@ex>")
        table = _build_id_table([parent, child])
        _build_references(table, [parent, child])
        assert table["<child@ex>"].parent is table["<parent@ex>"]
        assert table["<child@ex>"] in table["<parent@ex>"].children

    def test_references_header_chain(self) -> None:
        """References: <a> <b> <c> means a->b->c, and c is parent of current message."""
        msgs = [
            _make_message(message_id_header="<a@ex>"),
            _make_message(message_id_header="<b@ex>"),
            _make_message(message_id_header="<c@ex>"),
            _make_message(
                message_id_header="<d@ex>",
                references_header=["<a@ex>", "<b@ex>", "<c@ex>"],
            ),
        ]
        table = _build_id_table(msgs)
        _build_references(table, msgs)
        # a -> b -> c -> d
        assert table["<b@ex>"].parent is table["<a@ex>"]
        assert table["<c@ex>"].parent is table["<b@ex>"]
        assert table["<d@ex>"].parent is table["<c@ex>"]

    def test_ghost_parent_created_for_unknown_reference(self) -> None:
        """If References mentions a message we haven't seen, create a ghost container."""
        child = _make_message(
            message_id_header="<child@ex>",
            references_header=["<unknown@ex>"],
        )
        table = _build_id_table([child])
        _build_references(table, [child])
        assert "<unknown@ex>" in table
        assert table["<unknown@ex>"].message is None
        assert table["<unknown@ex>"].is_ghost is True
        assert table["<child@ex>"].parent is table["<unknown@ex>"]

    def test_circular_reference_prevented(self) -> None:
        """A->B->A should not create a loop; the cycle-creating link is skipped."""
        msg_a = _make_message(
            message_id_header="<a@ex>",
            references_header=["<b@ex>"],
        )
        msg_b = _make_message(
            message_id_header="<b@ex>",
            references_header=["<a@ex>"],
        )
        table = _build_id_table([msg_a, msg_b])
        _build_references(table, [msg_a, msg_b])
        # One of them should be parent of the other, but no cycle
        # Walk parent chain and confirm we don't loop
        visited: set[str] = set()
        node = table["<a@ex>"]
        while node is not None:
            assert node.message_id not in visited, "Cycle detected!"
            visited.add(node.message_id)
            node = node.parent

    def test_in_reply_to_appended_to_references(self) -> None:
        """In-Reply-To is used as final reference if not already present."""
        msg = _make_message(
            message_id_header="<child@ex>",
            references_header=["<ref@ex>"],
            in_reply_to="<parent@ex>",
        )
        table = _build_id_table([msg])
        _build_references(table, [msg])
        # ref -> parent -> child
        assert table["<child@ex>"].parent is table["<parent@ex>"]

    def test_in_reply_to_already_in_references_not_duplicated(self) -> None:
        """If In-Reply-To is already the last reference, don't add it again."""
        msg = _make_message(
            message_id_header="<child@ex>",
            references_header=["<a@ex>", "<parent@ex>"],
            in_reply_to="<parent@ex>",
        )
        table = _build_id_table([msg])
        _build_references(table, [msg])
        # a -> parent -> child
        assert table["<child@ex>"].parent is table["<parent@ex>"]
        assert table["<parent@ex>"].parent is table["<a@ex>"]

    def test_message_with_no_references(self) -> None:
        """Message with neither References nor In-Reply-To stays parentless."""
        msg = _make_message(message_id_header="<alone@ex>")
        table = _build_id_table([msg])
        _build_references(table, [msg])
        assert table["<alone@ex>"].parent is None

    def test_only_in_reply_to_no_references(self) -> None:
        """Message with In-Reply-To but no References header."""
        msg = _make_message(
            message_id_header="<child@ex>",
            in_reply_to="<parent@ex>",
        )
        table = _build_id_table([msg])
        _build_references(table, [msg])
        assert table["<child@ex>"].parent is table["<parent@ex>"]

    def test_self_reference_ignored(self) -> None:
        """A message referencing itself should not create a self-loop."""
        msg = _make_message(
            message_id_header="<self@ex>",
            in_reply_to="<self@ex>",
        )
        table = _build_id_table([msg])
        _build_references(table, [msg])
        # Should not be its own parent
        assert table["<self@ex>"].parent is None

    def test_set_parent_self_is_noop(self) -> None:
        """Calling _set_parent(x, x) is a no-op."""
        from app.services.threading import _set_parent

        c = Container(message_id="<a@ex>", message=_make_message(message_id_header="<a@ex>"))
        _set_parent(c, c)
        assert c.parent is None
        assert c.children == []

    def test_reparenting_removes_from_old_parent(self) -> None:
        """When a container gets a new parent, it is removed from the old parent's children."""
        msg_a = _make_message(message_id_header="<a@ex>")
        msg_b = _make_message(message_id_header="<b@ex>")
        msg_c = _make_message(
            message_id_header="<c@ex>",
            in_reply_to="<a@ex>",
        )
        table = _build_id_table([msg_a, msg_b, msg_c])
        _build_references(table, [msg_a, msg_b, msg_c])
        # c is child of a
        assert table["<c@ex>"].parent is table["<a@ex>"]
        # Now manually reparent c under b using _set_parent
        from app.services.threading import _set_parent

        _set_parent(table["<c@ex>"], table["<b@ex>"])
        # c should now be child of b, removed from a's children
        assert table["<c@ex>"].parent is table["<b@ex>"]
        assert table["<c@ex>"] not in table["<a@ex>"].children
        assert table["<c@ex>"] in table["<b@ex>"].children

    def test_ghost_created_in_build_references_for_unknown_ref(self) -> None:
        """When _build_references encounters a ref not in the table, it creates a ghost."""
        msg = _make_message(
            message_id_header="<child@ex>",
            references_header=["<unknown@ex>"],
        )
        # Manually build a table WITHOUT the ghost (simulating external usage)
        table: dict[str, Container] = {
            "<child@ex>": Container(message_id="<child@ex>", message=msg),
        }
        _build_references(table, [msg])
        assert "<unknown@ex>" in table
        assert table["<unknown@ex>"].is_ghost is True


# ===========================================================================
# 4. _find_root_set()  (Phase 3)
# ===========================================================================


class TestFindRootSet:
    """Phase 3: Find containers that have no parent."""

    def test_single_root(self) -> None:
        msg = _make_message(message_id_header="<root@ex>")
        table = _build_id_table([msg])
        _build_references(table, [msg])
        roots = _find_root_set(table)
        assert len(roots) == 1
        assert roots[0].message_id == "<root@ex>"

    def test_two_separate_roots(self) -> None:
        msgs = [
            _make_message(message_id_header="<a@ex>"),
            _make_message(message_id_header="<b@ex>"),
        ]
        table = _build_id_table(msgs)
        _build_references(table, msgs)
        roots = _find_root_set(table)
        root_ids = {r.message_id for r in roots}
        assert root_ids == {"<a@ex>", "<b@ex>"}

    def test_child_is_not_root(self) -> None:
        parent = _make_message(message_id_header="<parent@ex>")
        child = _make_message(
            message_id_header="<child@ex>",
            in_reply_to="<parent@ex>",
        )
        table = _build_id_table([parent, child])
        _build_references(table, [parent, child])
        roots = _find_root_set(table)
        assert len(roots) == 1
        assert roots[0].message_id == "<parent@ex>"


# ===========================================================================
# 5. _prune_empty()  (Phase 4)
# ===========================================================================


class TestPruneEmpty:
    """Phase 4: Remove/promote ghost containers."""

    def test_ghost_no_children_removed(self) -> None:
        """Ghost with no children should be removed entirely."""
        ghost = Container(message_id="<ghost@ex>", message=None, is_ghost=True)
        roots = _prune_empty([ghost])
        assert len(roots) == 0

    def test_ghost_one_child_promoted(self) -> None:
        """Ghost with exactly one child: child replaces ghost at root level."""
        ghost = Container(message_id="<ghost@ex>", message=None, is_ghost=True)
        child_msg = _make_message(message_id_header="<child@ex>")
        child = Container(message_id="<child@ex>", message=child_msg, is_ghost=False)
        ghost.children.append(child)
        child.parent = ghost

        roots = _prune_empty([ghost])
        assert len(roots) == 1
        assert roots[0].message_id == "<child@ex>"
        assert roots[0].parent is None

    def test_ghost_multiple_children_kept(self) -> None:
        """Ghost with multiple children is kept as a structural node."""
        ghost = Container(message_id="<ghost@ex>", message=None, is_ghost=True)
        child1 = Container(
            message_id="<c1@ex>",
            message=_make_message(message_id_header="<c1@ex>"),
            is_ghost=False,
        )
        child2 = Container(
            message_id="<c2@ex>",
            message=_make_message(message_id_header="<c2@ex>"),
            is_ghost=False,
        )
        ghost.children.extend([child1, child2])
        child1.parent = ghost
        child2.parent = ghost

        roots = _prune_empty([ghost])
        assert len(roots) == 1
        assert roots[0].message_id == "<ghost@ex>"
        assert len(roots[0].children) == 2

    def test_non_ghost_root_preserved(self) -> None:
        """A real message root is never removed."""
        msg = _make_message(message_id_header="<real@ex>")
        root = Container(message_id="<real@ex>", message=msg, is_ghost=False)
        roots = _prune_empty([root])
        assert len(roots) == 1
        assert roots[0].message_id == "<real@ex>"

    def test_nested_ghost_pruning(self) -> None:
        """Ghost -> ghost -> real message: intermediate ghosts should be pruned."""
        ghost1 = Container(message_id="<g1@ex>", message=None, is_ghost=True)
        ghost2 = Container(message_id="<g2@ex>", message=None, is_ghost=True)
        real = Container(
            message_id="<real@ex>",
            message=_make_message(message_id_header="<real@ex>"),
            is_ghost=False,
        )
        ghost1.children.append(ghost2)
        ghost2.parent = ghost1
        ghost2.children.append(real)
        real.parent = ghost2

        roots = _prune_empty([ghost1])
        assert len(roots) == 1
        assert roots[0].message_id == "<real@ex>"
        assert roots[0].parent is None

    def test_inner_ghost_no_children_removed(self) -> None:
        """Ghost child of a real root with no grandchildren is removed."""
        root_msg = _make_message(message_id_header="<root@ex>")
        root = Container(message_id="<root@ex>", message=root_msg, is_ghost=False)
        ghost_child = Container(message_id="<ghost@ex>", message=None, is_ghost=True)
        root.children.append(ghost_child)
        ghost_child.parent = root

        roots = _prune_empty([root])
        assert len(roots) == 1
        assert roots[0].message_id == "<root@ex>"
        assert len(roots[0].children) == 0

    def test_inner_ghost_one_child_promoted(self) -> None:
        """Ghost child of a real root with one grandchild: grandchild promoted."""
        root_msg = _make_message(message_id_header="<root@ex>")
        root = Container(message_id="<root@ex>", message=root_msg, is_ghost=False)
        ghost_child = Container(message_id="<ghost@ex>", message=None, is_ghost=True)
        grandchild_msg = _make_message(message_id_header="<gc@ex>")
        grandchild = Container(message_id="<gc@ex>", message=grandchild_msg, is_ghost=False)
        root.children.append(ghost_child)
        ghost_child.parent = root
        ghost_child.children.append(grandchild)
        grandchild.parent = ghost_child

        roots = _prune_empty([root])
        assert len(roots) == 1
        assert len(roots[0].children) == 1
        assert roots[0].children[0].message_id == "<gc@ex>"
        assert roots[0].children[0].parent is root


# ===========================================================================
# 6. _group_by_subject()  (Phase 5)
# ===========================================================================


class TestGroupBySubject:
    """Phase 5: Merge roots with same normalized subject within time window."""

    def test_same_subject_within_window_merged(self) -> None:
        msg1 = _make_message(
            message_id_header="<a@ex>",
            subject="Project Update",
            date=_NOW,
        )
        msg2 = _make_message(
            message_id_header="<b@ex>",
            subject="Re: Project Update",
            date=_NOW + timedelta(hours=24),
        )
        root1 = Container(message_id="<a@ex>", message=msg1, is_ghost=False)
        root2 = Container(message_id="<b@ex>", message=msg2, is_ghost=False)
        result = _group_by_subject([root1, root2])
        assert len(result) == 1

    def test_same_subject_outside_window_not_merged(self) -> None:
        msg1 = _make_message(
            message_id_header="<a@ex>",
            subject="Project Update",
            date=_NOW,
        )
        msg2 = _make_message(
            message_id_header="<b@ex>",
            subject="Re: Project Update",
            date=_NOW + timedelta(hours=100),
        )
        root1 = Container(message_id="<a@ex>", message=msg1, is_ghost=False)
        root2 = Container(message_id="<b@ex>", message=msg2, is_ghost=False)
        result = _group_by_subject([root1, root2])
        assert len(result) == 2

    def test_different_subjects_not_merged(self) -> None:
        msg1 = _make_message(message_id_header="<a@ex>", subject="Topic A")
        msg2 = _make_message(message_id_header="<b@ex>", subject="Topic B")
        root1 = Container(message_id="<a@ex>", message=msg1, is_ghost=False)
        root2 = Container(message_id="<b@ex>", message=msg2, is_ghost=False)
        result = _group_by_subject([root1, root2])
        assert len(result) == 2

    def test_ghost_root_replaced_by_real_root_on_merge(self) -> None:
        """When merging, prefer the root that has a real message over a ghost.

        The ghost root has an earlier date (via its child), so it sorts first as
        the base. The real root is the candidate. Lines 374-380 handle swapping
        the ghost base for the real candidate.
        """
        # Ghost root: its child has an earlier date so the ghost sorts first
        ghost_child_msg = _make_message(
            message_id_header="<gc@ex>",
            subject="Re: Topic",
            date=_NOW,  # earliest
        )
        ghost_root = Container(message_id="<ghost@ex>", message=None, is_ghost=True)
        ghost_child = Container(message_id="<gc@ex>", message=ghost_child_msg, is_ghost=False)
        ghost_root.children.append(ghost_child)
        ghost_child.parent = ghost_root

        # Real root: has a later date
        real_msg = _make_message(
            message_id_header="<real@ex>",
            subject="Topic",
            date=_NOW + timedelta(hours=1),
        )
        real_root = Container(message_id="<real@ex>", message=real_msg, is_ghost=False)

        result = _group_by_subject([ghost_root, real_root])
        assert len(result) == 1
        # The real root should be the surviving root (swapped in)
        surviving = result[0]
        assert surviving.message is not None
        assert surviving.message_id == "<real@ex>"

    def test_three_roots_same_subject_merged(self) -> None:
        msgs = [
            _make_message(
                message_id_header=f"<m{i}@ex>",
                subject="Topic" if i == 0 else "Re: Topic",
                date=_NOW + timedelta(hours=i),
            )
            for i in range(3)
        ]
        roots = [
            Container(message_id=f"<m{i}@ex>", message=msgs[i], is_ghost=False) for i in range(3)
        ]
        result = _group_by_subject(roots)
        assert len(result) == 1

    def test_empty_subject_not_grouped(self) -> None:
        """Messages with empty normalized subjects should NOT be merged together."""
        msg1 = _make_message(message_id_header="<a@ex>", subject="Re:")
        msg2 = _make_message(message_id_header="<b@ex>", subject="Fwd:")
        root1 = Container(message_id="<a@ex>", message=msg1, is_ghost=False)
        root2 = Container(message_id="<b@ex>", message=msg2, is_ghost=False)
        result = _group_by_subject([root1, root2])
        assert len(result) == 2

    def test_custom_time_window(self) -> None:
        msg1 = _make_message(
            message_id_header="<a@ex>",
            subject="Topic",
            date=_NOW,
        )
        msg2 = _make_message(
            message_id_header="<b@ex>",
            subject="Re: Topic",
            date=_NOW + timedelta(hours=50),
        )
        root1 = Container(message_id="<a@ex>", message=msg1, is_ghost=False)
        root2 = Container(message_id="<b@ex>", message=msg2, is_ghost=False)
        # With 24-hour window, they should NOT merge
        result = _group_by_subject([root1, root2], time_window_hours=24)
        assert len(result) == 2
        # With 72-hour window (default), they SHOULD merge
        # Reset parent links from prior grouping attempt
        root1 = Container(message_id="<a@ex>", message=msg1, is_ghost=False)
        root2 = Container(message_id="<b@ex>", message=msg2, is_ghost=False)
        result = _group_by_subject([root1, root2], time_window_hours=72)
        assert len(result) == 1


# ===========================================================================
# 7. Full Algorithm Integration (in-memory, no DB)
# ===========================================================================


class TestFullAlgorithm:
    """End-to-end threading algorithm tests with in-memory messages."""

    def test_simple_thread_3_messages(self) -> None:
        """3 messages with In-Reply-To chain -> 1 thread, depths 0/1/2."""
        group_id = uuid.uuid4()
        msg1 = _make_message(
            message_id_header="<m1@ex>",
            subject="Hello",
            group_id=group_id,
            date=_NOW,
        )
        msg2 = _make_message(
            message_id_header="<m2@ex>",
            subject="Re: Hello",
            in_reply_to="<m1@ex>",
            group_id=group_id,
            date=_NOW + timedelta(hours=1),
        )
        msg3 = _make_message(
            message_id_header="<m3@ex>",
            subject="Re: Re: Hello",
            in_reply_to="<m2@ex>",
            references_header=["<m1@ex>", "<m2@ex>"],
            group_id=group_id,
            date=_NOW + timedelta(hours=2),
        )
        messages = [msg1, msg2, msg3]
        table = _build_id_table(messages)
        _build_references(table, messages)
        roots = _find_root_set(table)
        roots = _prune_empty(roots)
        roots = _group_by_subject(roots)

        assert len(roots) == 1
        root = roots[0]
        assert root.message_id == "<m1@ex>"
        assert len(root.children) == 1
        assert root.children[0].message_id == "<m2@ex>"
        assert len(root.children[0].children) == 1
        assert root.children[0].children[0].message_id == "<m3@ex>"

    def test_single_message_thread(self) -> None:
        """One message with no references -> 1 root, 1 thread."""
        msg = _make_message(message_id_header="<solo@ex>")
        table = _build_id_table([msg])
        _build_references(table, [msg])
        roots = _find_root_set(table)
        roots = _prune_empty(roots)
        assert len(roots) == 1
        assert roots[0].message_id == "<solo@ex>"
        assert len(roots[0].children) == 0

    def test_deep_thread_50_plus_messages(self) -> None:
        """Chain of >50 messages -> correct depths without stack issues."""
        group_id = uuid.uuid4()
        messages: list[Message] = []
        for i in range(55):
            msg = _make_message(
                message_id_header=f"<m{i}@ex>",
                subject="Deep" if i == 0 else "Re: Deep",
                in_reply_to=f"<m{i - 1}@ex>" if i > 0 else None,
                group_id=group_id,
                date=_NOW + timedelta(minutes=i),
            )
            messages.append(msg)

        table = _build_id_table(messages)
        _build_references(table, messages)
        roots = _find_root_set(table)
        roots = _prune_empty(roots)

        assert len(roots) == 1
        # Walk the chain and verify depth
        node = roots[0]
        depth = 0
        while node.children:
            assert len(node.children) == 1
            node = node.children[0]
            depth += 1
        assert depth == 54  # 55 messages, root at depth 0

    def test_ghost_message_in_thread(self) -> None:
        """Message references an unknown parent -> ghost container created."""
        msg = _make_message(
            message_id_header="<child@ex>",
            in_reply_to="<missing@ex>",
        )
        table = _build_id_table([msg])
        _build_references(table, [msg])
        roots = _find_root_set(table)

        # Ghost for <missing@ex> is the root
        assert len(roots) == 1
        root = roots[0]
        assert root.message_id == "<missing@ex>"
        assert root.is_ghost is True
        assert root.message is None
        assert len(root.children) == 1
        assert root.children[0].message_id == "<child@ex>"

    def test_subject_fallback_merges_threads(self) -> None:
        """Two messages same subject no References within 72h -> merged."""
        group_id = uuid.uuid4()
        msg1 = _make_message(
            message_id_header="<a@ex>",
            subject="Budget Discussion",
            group_id=group_id,
            date=_NOW,
        )
        msg2 = _make_message(
            message_id_header="<b@ex>",
            subject="Re: Budget Discussion",
            group_id=group_id,
            date=_NOW + timedelta(hours=2),
        )
        messages = [msg1, msg2]
        table = _build_id_table(messages)
        _build_references(table, messages)
        roots = _find_root_set(table)
        roots = _prune_empty(roots)
        roots = _group_by_subject(roots)

        assert len(roots) == 1

    def test_subject_fallback_rejects_distant_messages(self) -> None:
        """Two messages same subject but >72h apart -> separate threads."""
        group_id = uuid.uuid4()
        msg1 = _make_message(
            message_id_header="<a@ex>",
            subject="Budget Discussion",
            group_id=group_id,
            date=_NOW,
        )
        msg2 = _make_message(
            message_id_header="<b@ex>",
            subject="Re: Budget Discussion",
            group_id=group_id,
            date=_NOW + timedelta(hours=100),
        )
        messages = [msg1, msg2]
        table = _build_id_table(messages)
        _build_references(table, messages)
        roots = _find_root_set(table)
        roots = _prune_empty(roots)
        roots = _group_by_subject(roots)

        assert len(roots) == 2


# ===========================================================================
# 8. Container dataclass
# ===========================================================================


class TestContainerSubject:
    """Tests for _container_subject helper."""

    def test_subject_from_real_message(self) -> None:
        from app.services.threading import _container_subject

        msg = _make_message(message_id_header="<a@ex>", subject="Hello World")
        c = Container(message_id="<a@ex>", message=msg, is_ghost=False)
        assert _container_subject(c) == "Hello World"

    def test_subject_from_ghost_with_child(self) -> None:
        from app.services.threading import _container_subject

        ghost = Container(message_id="<ghost@ex>", message=None, is_ghost=True)
        child_msg = _make_message(message_id_header="<child@ex>", subject="From Child")
        child = Container(message_id="<child@ex>", message=child_msg, is_ghost=False)
        ghost.children.append(child)
        assert _container_subject(ghost) == "From Child"

    def test_subject_from_ghost_with_nested_ghosts(self) -> None:
        """Ghost -> ghost -> real: subject comes from the deeply nested real message."""
        from app.services.threading import _container_subject

        ghost1 = Container(message_id="<g1@ex>", message=None, is_ghost=True)
        ghost2 = Container(message_id="<g2@ex>", message=None, is_ghost=True)
        real_msg = _make_message(message_id_header="<real@ex>", subject="Deep Subject")
        real = Container(message_id="<real@ex>", message=real_msg, is_ghost=False)
        ghost1.children.append(ghost2)
        ghost2.children.append(real)
        assert _container_subject(ghost1) == "Deep Subject"

    def test_subject_from_empty_ghost(self) -> None:
        """Ghost with no children returns empty string."""
        from app.services.threading import _container_subject

        ghost = Container(message_id="<ghost@ex>", message=None, is_ghost=True)
        assert _container_subject(ghost) == ""


class TestContainer:
    """Tests for the Container dataclass structure."""

    def test_container_defaults(self) -> None:
        c = Container(message_id="<test@ex>")
        assert c.message is None
        assert c.parent is None
        assert c.children == []
        assert c.is_ghost is True  # No message means ghost

    def test_container_with_message(self) -> None:
        msg = _make_message(message_id_header="<test@ex>")
        c = Container(message_id="<test@ex>", message=msg, is_ghost=False)
        assert c.message is msg
        assert c.is_ghost is False


# ===========================================================================
# 9. thread_messages() — DB integration
# ===========================================================================


class TestThreadMessagesDBIntegration:
    """Tests for the main thread_messages() function with mocked DB."""

    @pytest.fixture()
    def mock_session(self) -> AsyncMock:
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.add_all = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_simple_thread_persisted(self, mock_session: AsyncMock) -> None:
        """3-message thread is correctly persisted to DB."""
        group_id = uuid.uuid4()
        msg1 = _make_message(
            message_id_header="<m1@ex>",
            subject="Hello",
            group_id=group_id,
            date=_NOW,
            sender_email="alice@ex.com",
        )
        msg2 = _make_message(
            message_id_header="<m2@ex>",
            subject="Re: Hello",
            in_reply_to="<m1@ex>",
            group_id=group_id,
            date=_NOW + timedelta(hours=1),
            sender_email="bob@ex.com",
        )
        msg3 = _make_message(
            message_id_header="<m3@ex>",
            subject="Re: Hello",
            in_reply_to="<m2@ex>",
            references_header=["<m1@ex>", "<m2@ex>"],
            group_id=group_id,
            date=_NOW + timedelta(hours=2),
            sender_email="alice@ex.com",
        )
        messages = [msg1, msg2, msg3]

        # Mock the DB query to return our messages
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = messages
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        threads = await thread_messages(group_id, mock_session)

        assert len(threads) == 1
        thread = threads[0]
        assert thread.group_id == group_id
        assert thread.message_count == 3
        assert thread.participant_count == 2  # alice and bob
        assert thread.last_message_at == _NOW + timedelta(hours=2)
        assert normalize_subject(thread.subject) == normalize_subject("Hello")

        # Verify processing status updated
        for msg in messages:
            assert msg.processing_status == MessageProcessingStatus.threaded

    @pytest.mark.asyncio
    async def test_single_message_thread_persisted(self, mock_session: AsyncMock) -> None:
        """Single message -> 1 thread with count=1."""
        group_id = uuid.uuid4()
        msg = _make_message(
            message_id_header="<solo@ex>",
            subject="Standalone",
            group_id=group_id,
            date=_NOW,
            sender_email="carol@ex.com",
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        threads = await thread_messages(group_id, mock_session)

        assert len(threads) == 1
        assert threads[0].message_count == 1
        assert threads[0].participant_count == 1

    @pytest.mark.asyncio
    async def test_ghost_thread_message_single_child_pruned(self, mock_session: AsyncMock) -> None:
        """Ghost with single child gets pruned: child becomes root at depth 0."""
        group_id = uuid.uuid4()
        msg = _make_message(
            message_id_header="<child@ex>",
            subject="Reply to missing",
            in_reply_to="<missing@ex>",
            group_id=group_id,
            date=_NOW,
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        threads = await thread_messages(group_id, mock_session)

        assert len(threads) == 1
        assert threads[0].message_count == 1

        # Verify add_all was called with ThreadMessage objects
        add_all_calls = mock_session.add_all.call_args_list
        thread_messages_persisted: list[ThreadMessage] = []
        for call in add_all_calls:
            items = call[0][0]
            for item in items:
                if isinstance(item, ThreadMessage):
                    thread_messages_persisted.append(item)

        # Ghost with one child is pruned — only the real message remains
        assert len(thread_messages_persisted) == 1
        assert thread_messages_persisted[0].is_ghost is False
        assert thread_messages_persisted[0].depth == 0

    @pytest.mark.asyncio
    async def test_ghost_thread_message_multiple_children_kept(
        self, mock_session: AsyncMock
    ) -> None:
        """Ghost with multiple children is kept as structural node with is_ghost=True."""
        group_id = uuid.uuid4()
        # Two messages reply to the same missing parent
        msg1 = _make_message(
            message_id_header="<child1@ex>",
            subject="Reply A",
            in_reply_to="<missing@ex>",
            group_id=group_id,
            date=_NOW,
            sender_email="alice@ex.com",
        )
        msg2 = _make_message(
            message_id_header="<child2@ex>",
            subject="Reply A",
            in_reply_to="<missing@ex>",
            group_id=group_id,
            date=_NOW + timedelta(hours=1),
            sender_email="bob@ex.com",
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg1, msg2]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        threads = await thread_messages(group_id, mock_session)

        assert len(threads) == 1
        # Only real messages count
        assert threads[0].message_count == 2
        assert threads[0].participant_count == 2

        # Verify ghost ThreadMessage is created
        add_all_calls = mock_session.add_all.call_args_list
        thread_messages_persisted: list[ThreadMessage] = []
        for call in add_all_calls:
            items = call[0][0]
            for item in items:
                if isinstance(item, ThreadMessage):
                    thread_messages_persisted.append(item)

        ghosts = [tm for tm in thread_messages_persisted if tm.is_ghost]
        reals = [tm for tm in thread_messages_persisted if not tm.is_ghost]
        assert len(ghosts) == 1  # the missing parent
        assert len(reals) == 2  # the two real messages
        # Ghost is at depth 0, children at depth 1
        assert ghosts[0].depth == 0
        for real_tm in reals:
            assert real_tm.depth == 1

    @pytest.mark.asyncio
    async def test_no_messages_returns_empty(self, mock_session: AsyncMock) -> None:
        """No pending messages -> empty result."""
        group_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        threads = await thread_messages(group_id, mock_session)
        assert threads == []

    @pytest.mark.asyncio
    async def test_thread_counters_correct(self, mock_session: AsyncMock) -> None:
        """Verify message_count, participant_count, last_message_at."""
        group_id = uuid.uuid4()
        messages = [
            _make_message(
                message_id_header=f"<m{i}@ex>",
                subject="Topic" if i == 0 else "Re: Topic",
                in_reply_to=f"<m{i - 1}@ex>" if i > 0 else None,
                group_id=group_id,
                date=_NOW + timedelta(hours=i),
                sender_email=f"user{i % 3}@ex.com",
            )
            for i in range(5)
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = messages
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        threads = await thread_messages(group_id, mock_session)

        assert len(threads) == 1
        thread = threads[0]
        assert thread.message_count == 5
        assert thread.participant_count == 3  # user0, user1, user2
        assert thread.last_message_at == _NOW + timedelta(hours=4)

    @pytest.mark.asyncio
    async def test_processing_status_updated(self, mock_session: AsyncMock) -> None:
        """All processed messages should have status='threaded'."""
        group_id = uuid.uuid4()
        messages = [
            _make_message(
                message_id_header=f"<m{i}@ex>",
                group_id=group_id,
                date=_NOW + timedelta(hours=i),
            )
            for i in range(3)
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = messages
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await thread_messages(group_id, mock_session)

        for msg in messages:
            assert msg.processing_status == MessageProcessingStatus.threaded

    @pytest.mark.asyncio
    async def test_multiple_threads_from_unrelated_messages(self, mock_session: AsyncMock) -> None:
        """Messages with different subjects and no references -> separate threads."""
        group_id = uuid.uuid4()
        msg1 = _make_message(
            message_id_header="<a@ex>",
            subject="Topic Alpha",
            group_id=group_id,
            date=_NOW,
        )
        msg2 = _make_message(
            message_id_header="<b@ex>",
            subject="Topic Beta",
            group_id=group_id,
            date=_NOW,
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg1, msg2]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        threads = await thread_messages(group_id, mock_session)
        assert len(threads) == 2

    @pytest.mark.asyncio
    async def test_flush_called(self, mock_session: AsyncMock) -> None:
        """Verify session.flush() is called to persist changes."""
        group_id = uuid.uuid4()
        msg = _make_message(
            message_id_header="<a@ex>",
            group_id=group_id,
            date=_NOW,
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await thread_messages(group_id, mock_session)
        mock_session.flush.assert_awaited()
