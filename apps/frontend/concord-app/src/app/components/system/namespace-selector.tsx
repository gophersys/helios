import { useEffect, useState } from 'react';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { Select } from '../ui/select';
import { Namespace } from '../../types/models';

interface NamespaceSelectorProps {
  value: string;
  onChange: (ns: string) => void;
}

export function NamespaceSelector({ value, onChange }: NamespaceSelectorProps) {
  const [namespaces, setNamespaces] = useState<Namespace[]>([]);

  useEffect(() => {
    api<ApiResponse<Namespace[]>>('/v2/system/namespaces')
      .then((res) => setNamespaces(res.data))
      .catch(() => {});
  }, []);

  return (
    <Select
      compact
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Select namespace"
    >
      <option value="">All namespaces</option>
      {namespaces.map((ns) => (
        <option key={ns.name} value={ns.name}>
          {ns.name}
        </option>
      ))}
    </Select>
  );
}
