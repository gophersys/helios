import { useCallback, useState } from 'react';
import { Upload } from 'lucide-react';

interface ArtifactUploadProps {
  onUpload: (file: File) => Promise<void>;
  disabled?: boolean;
}

export function ArtifactUpload({ onUpload, disabled }: ArtifactUploadProps) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);

  const handleFile = useCallback(
    async (file: File) => {
      setUploading(true);
      try {
        await onUpload(file);
      } finally {
        setUploading(false);
      }
    },
    [onUpload]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      // Reset the input so the same file can be selected again
      e.target.value = '';
    },
    [handleFile]
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={[
        'flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-4 transition-colors',
        dragOver
          ? 'border-accent bg-accent-muted'
          : 'border-border bg-surface-0 hover:border-text-tertiary',
        disabled ? 'pointer-events-none opacity-50' : 'cursor-pointer',
      ].join(' ')}
    >
      <label className="flex cursor-pointer flex-col items-center gap-2">
        <input
          type="file"
          onChange={handleChange}
          className="hidden"
          disabled={disabled || uploading}
        />
        <Upload
          size={20}
          className="text-text-tertiary"
          strokeWidth={1.5}
        />
        <span className="text-2xs text-text-tertiary">
          {uploading ? 'Uploading...' : 'Drop file or click to upload'}
        </span>
      </label>
    </div>
  );
}
