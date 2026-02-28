/**
 * SearchFilters -- filter controls for search.
 *
 * Provides inputs for group, sender email, date from, and date to.
 * All filters are optional text/date inputs.
 */

"use client";

export interface SearchFilterValues {
  groupId: string;
  sender: string;
  dateFrom: string;
  dateTo: string;
}

interface SearchFiltersProps {
  filters: SearchFilterValues;
  onChange: (filters: SearchFilterValues) => void;
}

export function SearchFilters({ filters, onChange }: SearchFiltersProps) {
  function handleChange(field: keyof SearchFilterValues, value: string) {
    onChange({ ...filters, [field]: value });
  }

  return (
    <div className="flex flex-wrap gap-4">
      <div className="flex flex-col">
        <label
          htmlFor="search-group"
          className="text-xs font-medium text-gray-700"
        >
          Group
        </label>
        <input
          id="search-group"
          type="text"
          value={filters.groupId}
          onChange={(e) => handleChange("groupId", e.target.value)}
          className="mt-1 rounded-md border border-gray-300 px-2 py-1 text-sm"
        />
      </div>
      <div className="flex flex-col">
        <label
          htmlFor="search-sender"
          className="text-xs font-medium text-gray-700"
        >
          Sender
        </label>
        <input
          id="search-sender"
          type="text"
          value={filters.sender}
          onChange={(e) => handleChange("sender", e.target.value)}
          className="mt-1 rounded-md border border-gray-300 px-2 py-1 text-sm"
        />
      </div>
      <div className="flex flex-col">
        <label
          htmlFor="search-date-from"
          className="text-xs font-medium text-gray-700"
        >
          From
        </label>
        <input
          id="search-date-from"
          type="date"
          value={filters.dateFrom}
          onChange={(e) => handleChange("dateFrom", e.target.value)}
          className="mt-1 rounded-md border border-gray-300 px-2 py-1 text-sm"
        />
      </div>
      <div className="flex flex-col">
        <label
          htmlFor="search-date-to"
          className="text-xs font-medium text-gray-700"
        >
          To
        </label>
        <input
          id="search-date-to"
          type="date"
          value={filters.dateTo}
          onChange={(e) => handleChange("dateTo", e.target.value)}
          className="mt-1 rounded-md border border-gray-300 px-2 py-1 text-sm"
        />
      </div>
    </div>
  );
}
