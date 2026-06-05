import { DndContext, closestCenter } from '@dnd-kit/core'
import { arrayMove, SortableContext, verticalListSortingStrategy, useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical } from 'lucide-react'
import MLScoreBadge from '../recommendations/MLScoreBadge'

function SortableItem({ item, index }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.id })
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition }} className={`flex items-center gap-3 rounded-xl border bg-white p-4 ${isDragging ? 'scale-[1.01] shadow-xl' : ''}`}>
      <button {...attributes} {...listeners}><GripVertical className="h-4 w-4 text-muted" /></button>
      <span className="rounded-full bg-primary/10 px-2 py-1 text-xs font-bold text-primary">#{index + 1}</span>
      <div className="flex-1"><p className="font-semibold">{item.destination_name}</p><p className="text-xs text-muted">{item.estimated_budget_range}</p></div>
      <MLScoreBadge score={item.ml_score} />
    </div>
  )
}

export default function DraggableRankList({ items, setItems }) {
  return (
    <DndContext collisionDetection={closestCenter} onDragEnd={({ active, over }) => {
      if (!over || active.id === over.id) return
      const oldIndex = items.findIndex((i) => i.id === active.id)
      const newIndex = items.findIndex((i) => i.id === over.id)
      setItems(arrayMove(items, oldIndex, newIndex))
    }}>
      <SortableContext items={items.map((i) => i.id)} strategy={verticalListSortingStrategy}>
        <div className="space-y-3">{items.map((item, i) => <SortableItem key={item.id} item={item} index={i} />)}</div>
      </SortableContext>
    </DndContext>
  )
}
