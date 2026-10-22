import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import { perfilKeys } from '../hooks/usePerfil';
import { updateCorrectionProvider } from '../services/perfil-service';

const DEFAULT_MODEL = 'google/gemini-3.8-flash';

interface OpenRouterModelFieldProps {
  savedModel?: string | null;
}

export const OpenRouterModelField = ({ savedModel }: OpenRouterModelFieldProps) => {
  const initialModel = savedModel?.trim() || DEFAULT_MODEL;
  const [model, setModel] = useState(initialModel);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (value: string) => updateCorrectionProvider('openrouter', value),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: perfilKeys.all });
      toast.success('Modelo de OpenRouter guardado');
    },
  });
  const normalizedModel = model.trim() || DEFAULT_MODEL;

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate(normalizedModel);
      }}
      className="space-y-3"
    >
      <Input
        label="Modelo de OpenRouter"
        value={model}
        onChange={(event) => {
          setModel(event.target.value);
          mutation.reset();
        }}
        disabled={mutation.isPending}
        autoComplete="off"
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        placeholder={DEFAULT_MODEL}
        helperText={`Copiá el identificador de OpenRouter, por ejemplo anthropic/claude-sonnet-5.5. Dejá vacío para usar ${DEFAULT_MODEL}.`}
        error={mutation.error ? mutation.error.message || 'No se pudo guardar el modelo. Intentá nuevamente.' : undefined}
      />
      <Button
        type="submit"
        disabled={mutation.isPending || normalizedModel === initialModel}
        isLoading={mutation.isPending}
        className="w-full sm:w-auto"
      >
        {mutation.isPending ? 'Guardando...' : 'Guardar modelo'}
      </Button>
    </form>
  );
};
