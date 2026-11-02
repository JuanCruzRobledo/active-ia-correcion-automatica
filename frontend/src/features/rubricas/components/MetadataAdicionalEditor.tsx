import { KeyValueInput } from '@/shared/components/ui/KeyValueInput';

interface MetadataAdicionalEditorProps {
  metadata: Record<string, unknown>;
  onChange: (metadata: Record<string, unknown>) => void;
}

/** La política estructurada se edita aparte y no debe convertirse en texto. */
export function MetadataAdicionalEditor({ metadata, onChange }: MetadataAdicionalEditorProps) {
  const adicionales = Object.fromEntries(
    Object.entries(metadata).filter(([key]) => key !== 'politica_entrega'),
  );

  return (
    <KeyValueInput
      value={adicionales}
      onChange={(value) => onChange({
        ...value,
        ...('politica_entrega' in metadata ? { politica_entrega: metadata.politica_entrega } : {}),
      })}
      placeholder={{ key: 'lenguaje', value: 'JavaScript' }}
    />
  );
}
