import { useCallback, useState } from 'react';
import { Upload, X } from 'lucide-react';

interface ImageUploadProps {
  currentUrl?: string | null;
  onUpload: (file: File) => Promise<void>;
  disabled?: boolean;
}

export function ImageUpload({ currentUrl, onUpload, disabled }: ImageUploadProps) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (!ext || !['png', 'jpg', 'jpeg', 'webp'].includes(ext)) {
        return;
      }
      setPreview(URL.createObjectURL(file));
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
    },
    [handleFile]
  );

  const displayUrl = preview || currentUrl;

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={[
        'relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed transition-colors',
        dragOver
          ? 'border-accent bg-accent-muted'
          : 'border-border bg-surface-0 hover:border-text-tertiary',
        disabled ? 'pointer-events-none opacity-50' : 'cursor-pointer',
        displayUrl ? 'h-40' : 'h-32',
      ].join(' ')}
    >
      {displayUrl ? (
        <>
          <img
            src={displayUrl}
            alt="Hero"
            className="h-full w-full rounded-lg object-contain"
          />
          {!disabled && (
            <label className="absolute inset-0 flex cursor-pointer items-center justify-center rounded-lg bg-overlay opacity-0 transition-opacity hover:opacity-100">
              <input
                type="file"
                accept=".png,.jpg,.jpeg,.webp"
                onChange={handleChange}
                className="hidden"
              />
              <span className="text-xs font-medium text-white">
                {uploading ? 'Uploading...' : 'Replace image'}
              </span>
            </label>
          )}
        </>
      ) : (
        <label className="flex cursor-pointer flex-col items-center gap-2 p-4">
          <input
            type="file"
            accept=".png,.jpg,.jpeg,.webp"
            onChange={handleChange}
            className="hidden"
          />
          <Upload
            size={20}
            className="text-text-tertiary"
            strokeWidth={1.5}
          />
          <span className="text-2xs text-text-tertiary">
            {uploading ? 'Uploading...' : 'Drop image or click to upload'}
          </span>
        </label>
      )}
    </div>
  );
}
