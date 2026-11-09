'use client'

import { ImageIcon, X } from 'lucide-react'
import { useId, useRef, useState, type DragEvent } from 'react'
import { formatFileSize, isAcceptedImage } from '@/lib/analysis/format'
import type { PanelImage } from '@/lib/analysis/types'
import { cn } from '@/lib/utils'

type ComicPanelUploaderProps = {
  number: '01' | '02'
  ordinal: 'first' | 'second'
  value: PanelImage | null
  disabled?: boolean
  onSelect: (file: File) => void
  onRemove: () => void
  onInvalid: () => void
}

export function ComicPanelUploader({
  number,
  ordinal,
  value,
  disabled,
  onSelect,
  onRemove,
  onInvalid,
}: ComicPanelUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const labelId = useId()
  const helpId = useId()

  const openPicker = () => {
    if (!disabled) inputRef.current?.click()
  }

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0]
    if (!file) return
    if (!isAcceptedImage(file)) {
      onInvalid()
      return
    }
    onSelect(file)
  }

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    if (disabled) return
    event.dataTransfer.dropEffect = 'copy'
    setIsDragging(true)
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
    if (!disabled) handleFiles(event.dataTransfer.files)
  }

  return (
    <div className="w-full min-w-0">
      <p
        id={labelId}
        className="mb-2.5 font-mono text-[11px] font-medium tracking-[0.14em] text-muted-foreground"
      >
        <span className="text-foreground">{number}</span> / {ordinal.toUpperCase()} PANEL
      </p>

      <div
        role="group"
        aria-labelledby={labelId}
        onClick={value ? undefined : openPicker}
        onDragOver={handleDragOver}
        onDragEnter={handleDragOver}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={cn(
          'group relative flex h-[200px] w-full items-center justify-center overflow-hidden rounded-sm border bg-card transition-colors sm:h-[220px] lg:h-[232px]',
          value ? 'border-border' : 'cursor-pointer border-dashed border-border-strong/70 hover:border-foreground/60',
          isDragging && 'border-solid border-teal bg-teal/[0.04]',
          disabled && 'pointer-events-none opacity-70',
        )}
      >
        {value ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element -- local object URL preview */}
            <img
              key={value.url}
              src={value.url}
              alt={`${ordinal === 'first' ? 'First' : 'Second'} comic panel: ${value.file.name}`}
              className="h-full w-full object-contain p-3 animate-in fade-in duration-500"
            />
            <div className="absolute top-2 right-2 flex items-center gap-1">
              <button
                type="button"
                onClick={openPicker}
                disabled={disabled}
                className="rounded-sm border border-border bg-card/95 px-2 py-1 text-xs text-foreground transition-colors hover:border-foreground/50 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring"
              >
                Replace
                <span className="sr-only"> {ordinal} panel</span>
              </button>
              <button
                type="button"
                onClick={onRemove}
                disabled={disabled}
                aria-label={`Remove ${ordinal} panel`}
                className="flex size-[26px] items-center justify-center rounded-sm border border-border bg-card/95 text-muted-foreground transition-colors hover:border-terracotta hover:text-terracotta focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring"
              >
                <X aria-hidden="true" className="size-3.5" />
              </button>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center px-6 text-center">
            <ImageIcon
              aria-hidden="true"
              className="size-5 text-muted-foreground transition-colors group-hover:text-foreground"
              strokeWidth={1.5}
            />
            <p className="mt-3 text-sm font-medium">
              {isDragging ? 'Drop image to add' : `Upload ${ordinal} panel`}
            </p>
            <p id={helpId} className="mt-1 font-mono text-[11px] text-muted-foreground">
              PNG, JPG or JPEG
            </p>
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation()
                openPicker()
              }}
              aria-describedby={helpId}
              className="mt-4 rounded-sm border border-border px-3 py-1.5 text-xs font-medium transition-colors hover:border-foreground/60 hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              Browse
              <span className="sr-only"> for {ordinal} panel, or drag and drop an image</span>
            </button>
          </div>
        )}

        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg,.png,.jpg,.jpeg"
          tabIndex={-1}
          aria-hidden="true"
          className="sr-only"
          onChange={(event) => {
            handleFiles(event.target.files)
            event.target.value = ''
          }}
        />
      </div>

      <p className="mt-2 flex h-4 items-center gap-2 font-mono text-[11px] text-muted-foreground">
        {value ? (
          <>
            <span className="truncate" title={value.file.name}>
              {value.file.name}
            </span>
            <span aria-hidden="true" className="shrink-0">
              ·
            </span>
            <span className="shrink-0">{formatFileSize(value.file.size)}</span>
          </>
        ) : null}
      </p>
    </div>
  )
}
