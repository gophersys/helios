import { useCallback, useState } from 'react';
import { Upload, X, Check } from 'lucide-react';
import { apiUpload } from '../../api';
import { Select } from '../../components/ui/select';
import { ErrorAlert } from '../../components/ui/error-alert';
import { BoardRevision } from '../../types/models';

export function FirmwareBuildUpload({
  productId,
  applicationId,
  boardRevisions,
  onClose,
  onSuccess,
}: {
  productId: string;
  applicationId: string;
  boardRevisions: BoardRevision[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const [version, setVersion] = useState('');
  const [majorVersion, setMajorVersion] = useState('0');
  const [minorVersion, setMinorVersion] = useState('0');
  const [buildNumber, setBuildNumber] = useState('0');
  const [boardRevisionId, setBoardRevisionId] = useState('');
  const [bootloaderId, setBootloaderId] = useState('');
  const [isManufacturing, setIsManufacturing] = useState(false);
  const [status, setStatus] = useState('DRAFT');
  const [notes, setNotes] = useState('');

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a file');
      return;
    }
    setError(null);
    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('applicationId', applicationId);
      formData.append('version', version);
      formData.append('majorVersion', majorVersion);
      formData.append('minorVersion', minorVersion);
      formData.append('buildNumber', buildNumber);
      if (boardRevisionId) formData.append('boardRevisionId', boardRevisionId);
      if (bootloaderId) formData.append('bootloaderId', bootloaderId);
      formData.append('isManufacturing', String(isManufacturing));
      formData.append('status', status);
      if (notes) formData.append('notes', notes);

      await apiUpload(`/v2/products/${productId}/firmware-builds/upload`, formData);
      onSuccess();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to upload firmware build');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="mb-4 rounded-lg border border-border bg-surface-0 p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-2xs font-medium text-text-secondary">Upload firmware build</span>
        <button onClick={onClose} className="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary">
          <X size={14} />
        </button>
      </div>

      <ErrorAlert message={error} />

      <form onSubmit={handleSubmit}>
        {/* File drop zone */}
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={() => setDragOver(false)}
          className={[
            'mb-3 flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors',
            dragOver ? 'border-accent bg-accent/5' : 'border-border',
            file ? 'bg-success-muted/10' : '',
          ].join(' ')}
        >
          <Upload size={20} className="mb-2 text-text-tertiary" />
          {file ? (
            <div className="text-center">
              <span className="text-sm font-medium text-text-primary">{file.name}</span>
              <span className="ml-2 text-2xs text-text-tertiary">
                ({(file.size / 1024).toFixed(1)} KB)
              </span>
              <button
                type="button"
                onClick={() => setFile(null)}
                className="ml-2 text-2xs text-error hover:underline"
              >
                Remove
              </button>
            </div>
          ) : (
            <div className="text-center">
              <label className="cursor-pointer text-sm text-accent hover:underline">
                Choose file
                <input
                  type="file"
                  className="hidden"
                  accept=".zip,.hex,.ckbin,.bin"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              </label>
              <span className="text-sm text-text-tertiary"> or drag and drop</span>
              <div className="mt-1 text-2xs text-text-tertiary">ZIP, HEX, CKBIN, or BIN files</div>
            </div>
          )}
        </div>

        {/* Metadata fields */}
        <div className="mb-3 grid grid-cols-4 gap-3">
          <div>
            <label className="mb-1 block text-2xs font-medium text-text-tertiary">Version</label>
            <input
              type="text"
              required
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="1.0.0"
              className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-2xs font-medium text-text-tertiary">Major</label>
            <input
              type="number"
              value={majorVersion}
              onChange={(e) => setMajorVersion(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-2xs font-medium text-text-tertiary">Minor</label>
            <input
              type="number"
              value={minorVersion}
              onChange={(e) => setMinorVersion(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-2xs font-medium text-text-tertiary">Build #</label>
            <input
              type="number"
              value={buildNumber}
              onChange={(e) => setBuildNumber(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
            />
          </div>
        </div>

        <div className="mb-3 grid grid-cols-3 gap-3">
          <div>
            <label className="mb-1 block text-2xs font-medium text-text-tertiary">Board Revision</label>
            <Select
              value={boardRevisionId}
              onChange={(e) => setBoardRevisionId(e.target.value)}
            >
              <option value="">None</option>
              {boardRevisions.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.version}{r.chipsets.length > 0 ? ` (${r.chipsets.join(', ')})` : ''}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-2xs font-medium text-text-tertiary">Bootloader ID</label>
            <input
              type="text"
              value={bootloaderId}
              onChange={(e) => setBootloaderId(e.target.value)}
              placeholder="Optional"
              className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-2xs font-medium text-text-tertiary">Status</label>
            <Select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="DRAFT">Draft</option>
              <option value="RELEASED">Released</option>
              <option value="DEPRECATED">Deprecated</option>
            </Select>
          </div>
        </div>

        <div className="mb-3 flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-text-primary">
            <input
              type="checkbox"
              checked={isManufacturing}
              onChange={(e) => setIsManufacturing(e.target.checked)}
              className="rounded border-border"
            />
            Manufacturing build
          </label>
        </div>

        <div className="mb-3">
          <label className="mb-1 block text-2xs font-medium text-text-tertiary">Notes</label>
          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional notes"
            className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </div>

        <div className="flex gap-2">
          <button
            type="submit"
            disabled={uploading || !file}
            className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            <Check size={12} />
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-1.5 text-2xs font-medium text-text-secondary hover:bg-surface-2"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
