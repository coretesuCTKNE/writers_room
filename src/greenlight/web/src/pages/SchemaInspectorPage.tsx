import { useEffect, useMemo, useState } from 'react';
import styled from '@emotion/styled';
import { Card } from '../components';
import { ErrorText, PageContainer, PageTitle } from '../components/layout.tsx';

const Subtitle = styled.p`
  color: var(--text-secondary);
  font-size: 13px;
  margin-top: 0;
`;

const Toolbar = styled.div`
  display: flex;
  gap: 8px;
  margin: 16px 0;
  flex-wrap: wrap;
`;

const SearchInput = styled.input`
  padding: 8px 12px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  font-size: 13px;
  min-width: 240px;

  &:focus {
    outline: none;
    border-color: var(--accent);
  }
`;

const Chip = styled.button<{ active?: boolean }>`
  padding: 6px 12px;
  background: ${({ active }) => (active ? 'var(--accent)' : 'var(--bg-elevated)')};
  color: ${({ active }) => (active ? 'var(--bg-base)' : 'var(--text-secondary)')};
  border: none;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;

  &:hover {
    color: ${({ active }) => (active ? 'var(--bg-base)' : 'var(--text-primary)')};
  }
`;

const TableGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
`;

const TableName = styled.div`
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 14px;
  color: var(--accent);
  margin-bottom: 4px;
`;

const TableMeta = styled.div`
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 10px;
`;

const ColRow = styled.div`
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 3px 0;
  font-family: var(--font-mono);
  font-size: 11px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);

  &:last-child {
    border-bottom: none;
  }
`;

const ColName = styled.span`
  color: var(--text-primary);
`;

const ColType = styled.span`
  color: var(--text-secondary);
`;

interface Column {
  name: string;
  type: string;
  default: string;
}

interface TableInfo {
  name: string;
  engine: string;
  row_count: number;
  size: string;
  columns: Column[];
}

type SortMode = 'name' | 'rows' | 'size';

function parseSize(s: string): number {
  const m = s.match(/^([\d.]+)\s*(B|KiB|MiB|GiB|TiB)$/);
  if (!m) return 0;
  const mult = { B: 1, KiB: 1024, MiB: 1024 ** 2, GiB: 1024 ** 3, TiB: 1024 ** 4 }[m[2]] ?? 1;
  return parseFloat(m[1]) * mult;
}

export function SchemaInspectorPage() {
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<SortMode>('name');
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    fetch('/api/system/schema')
      .then((r) => (r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)))
      .then((data) => setTables(data.tables))
      .catch((e) => setError(String(e)));
  };

  useEffect(load, []);

  const filtered = useMemo(() => {
    let out = tables.filter(
      (t) =>
        t.name.includes(query.toLowerCase()) ||
        t.columns.some((c) => c.name.includes(query.toLowerCase())),
    );
    if (sort === 'rows') out = [...out].sort((a, b) => b.row_count - a.row_count);
    else if (sort === 'size') out = [...out].sort((a, b) => parseSize(b.size) - parseSize(a.size));
    else out = [...out].sort((a, b) => a.name.localeCompare(b.name));
    return out;
  }, [tables, query, sort]);

  const totalRows = tables.reduce((acc, t) => acc + t.row_count, 0);

  return (
    <PageContainer className="schema-inspector-page">
      <PageTitle className="schema-inspector-page-title">Schema Inspector</PageTitle>
      <Subtitle className="schema-inspector-subtitle">
        Live ClickHouse schema — database <code style={{ color: 'var(--accent)' }}>greenlight</code>,{' '}
        {tables.length} tables, {totalRows.toLocaleString()} rows
      </Subtitle>

      <Toolbar className="schema-inspector-toolbar">
        <SearchInput className="schema-inspector-search" placeholder="Filter by table or column…" value={query} onChange={(e) => setQuery(e.target.value)} />
        <Chip className="schema-inspector-chip" active={sort === 'name'} onClick={() => setSort('name')}>
          A–Z
        </Chip>
        <Chip className="schema-inspector-chip" active={sort === 'rows'} onClick={() => setSort('rows')}>
          By rows
        </Chip>
        <Chip className="schema-inspector-chip" active={sort === 'size'} onClick={() => setSort('size')}>
          By size
        </Chip>
        <Chip className="schema-inspector-chip" onClick={load}>Refresh</Chip>
      </Toolbar>

      {error && (
        <Card padding="md" className="schema-inspector-error-card">
          <ErrorText>Failed to load schema: {error}</ErrorText>
        </Card>
      )}

      <TableGrid className="schema-inspector-table-grid">
        {filtered.map((t) => (
          <Card key={t.name} padding="md" className="schema-inspector-table-card">
            <TableName className="schema-inspector-table-name">{t.name}</TableName>
            <TableMeta className="schema-inspector-table-meta">
              {t.row_count.toLocaleString()} rows · {t.size} · {t.engine.replace(/(MergeTree|Engine).*/, '$1')}
            </TableMeta>
            <div className="schema-inspector-columns">
              {t.columns.map((c) => (
                <ColRow key={c.name} className="schema-inspector-col-row">
                  <ColName className="schema-inspector-col-name">{c.name}</ColName>
                  <ColType className="schema-inspector-col-type">{c.type}</ColType>
                </ColRow>
              ))}
            </div>
          </Card>
        ))}
      </TableGrid>
    </PageContainer>
  );
}
