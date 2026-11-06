import { useState, useCallback } from 'react';
import { Eye, Pencil, ListChecks, MessageSquare } from 'lucide-react';
import { Modal } from '../../../shared/components/ui/Modal';
import { Button } from '../../../shared/components/ui/Button';
import { Badge } from '../../../shared/components/ui/Badge';
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '../../../shared/components/ui/Accordion';
import { useUpdateCorreccion } from '../hooks/useCorrecciones';
import type { Correccion, CriterioEvaluado } from '../types';
import { actualizarSubcriterio, erroresSubcriterios, normalizarCriterios, sumarPuntajes } from '../utils/edicionSubcriterios';
import { CriterioCorreccionCard } from './CriterioCorreccionCard';
import { ListaComentariosCorreccion } from './ListaComentariosCorreccion';
import { AjustesCorreccion } from './AjustesCorreccion';
import { NotaCorreccion } from './NotaCorreccion';

interface CorreccionViewEditModalProps {
  correccion: Correccion;
  alumno: string;
  trabajoNombre: string;
  isOpen: boolean;
  onClose: () => void;
}

/** A new server snapshot or reopening starts a fresh editable copy. */
export default function CorreccionViewEditModal(props: CorreccionViewEditModalProps) {
  const [snapshot, setSnapshot] = useState(props.correccion);
  const [wasOpen, setWasOpen] = useState(props.isOpen);
  const [revision, setRevision] = useState(0);
  if (snapshot !== props.correccion || wasOpen !== props.isOpen) {
    setSnapshot(props.correccion); setWasOpen(props.isOpen); setRevision(revision + 1);
  }
  return <CorreccionForm key={revision} {...props} />;
}

function CorreccionForm({ correccion, alumno, trabajoNombre, isOpen, onClose }: CorreccionViewEditModalProps) {
  const [mode, setMode] = useState<'view' | 'edit'>('view');
  const [nota, setNota] = useState(Number(correccion.nota_academica ?? correccion.nota));
  const [criterios, setCriterios] = useState(() => normalizarCriterios(correccion.criterios));
  const [fortalezas, setFortalezas] = useState(correccion.fortalezas || []);
  const [recomendaciones, setRecomendaciones] = useState(correccion.recomendaciones || []);
  const [comentarioGeneral, setComentarioGeneral] = useState(correccion.comentario_general || '');
  const [cdAplicada, setCdAplicada] = useState(correccion.condicion_desaprobacion_aplicada);
  const [penalizaciones, setPenalizaciones] = useState(correccion.penalizaciones_aplicadas || []);
  const [resetKey, setResetKey] = useState(0);
  const updateMutation = useUpdateCorreccion();
  const errors = erroresSubcriterios(criterios);
  const invalid = Object.keys(errors).length > 0;
  const isViewMode = mode === 'view';
  const handleCancelar = () => {
    setNota(Number(correccion.nota_academica ?? correccion.nota));
    setCriterios(normalizarCriterios(correccion.criterios));
    setFortalezas(correccion.fortalezas || []); setRecomendaciones(correccion.recomendaciones || []);
    setComentarioGeneral(correccion.comentario_general || '');
    setCdAplicada(correccion.condicion_desaprobacion_aplicada); setPenalizaciones(correccion.penalizaciones_aplicadas || []);
    setResetKey(key => key + 1); setMode('view');
  };
  const handleClose = () => { if (!updateMutation.isPending) { handleCancelar(); onClose(); } };
  const handleCriterioChange = useCallback((id: string, field: keyof CriterioEvaluado, value: string | number) => {
    setCriterios(current => current.map(c => c.id === id ? { ...c, [field]: value } : c));
  }, []);
  const handleSubChange = useCallback((id: string, subId: string, field: 'puntaje_obtenido' | 'feedback', value: string | number) => {
    setCriterios(current => actualizarSubcriterio(current, id, subId, field, value, correccion.criterios));
  }, [correccion.criterios]);
  const recalcular = () => { if (!invalid) setNota(sumarPuntajes(criterios.map(c => c.puntaje_obtenido))); };
  const guardar = () => {
    if (invalid || updateMutation.isPending) return;
    updateMutation.mutate({ correccionId: correccion.id, data: {
      nota, nota_antes_penalizaciones: sumarPuntajes(criterios.map(c => c.puntaje_obtenido)),
      condicion_desaprobacion_aplicada: cdAplicada || null, penalizaciones_aplicadas: penalizaciones,
      criterios, fortalezas, recomendaciones, comentario_general: comentarioGeneral,
    } }, { onSuccess: () => setMode('view') });
  };
  return <Modal isOpen={isOpen} onClose={handleClose} size="2xl" title={`Corrección: ${alumno}`}>
    <fieldset disabled={updateMutation.isPending} className="min-w-0 border-0 p-0">
    <div className="flex items-center justify-between border-b border-border pb-4 mb-4 -mt-6">
      <p className="text-sm text-muted-foreground">{trabajoNombre}</p>
      <Button variant={isViewMode ? 'outline' : 'primary'} size="sm" className="gap-2"
        onClick={() => isViewMode ? setMode('edit') : handleCancelar()}>
        {isViewMode ? <><Pencil className="h-4 w-4" />Editar</> : <><Eye className="h-4 w-4" />Ver</>}
      </Button>
    </div>
    <div className="space-y-6 max-h-[calc(100vh-22rem)] overflow-y-auto pr-2">
      <NotaCorreccion correccion={correccion} nota={nota} isViewMode={isViewMode} setNota={setNota} handleRecalcularNota={recalcular} />
      {!isViewMode && <p className="text-xs text-muted-foreground">
        Editá el puntaje y comentario de cada subcriterio. El total del criterio se actualiza al cambiar sus puntajes.
        Usá Recalcular para llevar la suma de criterios a la nota académica; también podés ajustarla manualmente.
      </p>}
      <AjustesCorreccion correccion={correccion} cdAplicada={cdAplicada} penalizaciones={penalizaciones}
        isViewMode={isViewMode} setCdAplicada={setCdAplicada} setPenalizaciones={setPenalizaciones} handleRecalcularNota={recalcular} />
      <Accordion defaultValue={['criterios']}>
        <AccordionItem value="criterios">
          <AccordionTrigger value="criterios" icon={<ListChecks className="h-5 w-5" />}
            badge={<Badge variant="outline" className="ml-2">{criterios.length} criterios</Badge>}>Criterios de Evaluación</AccordionTrigger>
          <AccordionContent value="criterios">
            {criterios.length ? <div className="space-y-3">{criterios.map(c => <CriterioCorreccionCard key={c.id}
              criterio={c} isViewMode={isViewMode} errors={errors} onChange={handleCriterioChange} onSubChange={handleSubChange} />)}</div> :
              <p className="text-sm text-muted-foreground text-center py-8">No hay criterios de evaluación</p>}
          </AccordionContent>
        </AccordionItem>
        <ListaComentariosCorreccion key={`fortalezas-${resetKey}`} kind="fortalezas" items={fortalezas} isViewMode={isViewMode} onChange={setFortalezas} />
        <ListaComentariosCorreccion key={`recomendaciones-${resetKey}`} kind="recomendaciones" items={recomendaciones} isViewMode={isViewMode} onChange={setRecomendaciones} />
        <AccordionItem value="comentario">
          <AccordionTrigger value="comentario" icon={<MessageSquare className="h-5 w-5" />}>Comentario General</AccordionTrigger>
          <AccordionContent value="comentario"><textarea aria-label="Comentario General" value={comentarioGeneral}
            onChange={e => setComentarioGeneral(e.target.value)} disabled={isViewMode} rows={4}
            className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm disabled:bg-muted/30"
            placeholder={isViewMode ? 'Sin comentario general' : 'Escribe un comentario general para el alumno...'} /></AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
    {!isViewMode && <div className="flex items-center justify-end gap-3 border-t border-border pt-4 mt-6">
      <Button variant="ghost" onClick={handleCancelar}>Cancelar</Button>
      <Button variant="primary" onClick={guardar} disabled={invalid || updateMutation.isPending} isLoading={updateMutation.isPending}>Guardar Cambios</Button>
    </div>}
    </fieldset>
  </Modal>;
}
