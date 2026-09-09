import styled from '@emotion/styled';
import { useRef, useState } from 'react';

const UploadZone_ = styled.div<{ isDragging: boolean }>`
  border: 2px dashed ${({ isDragging }) =>
    isDragging ? 'var(--accent)' : 'var(--bg-elevated)'};
  border-radius: var(--radius);
  padding: 48px;
  text-align: center;
  cursor: pointer;
  transition: all var(--transition);
  background: ${({ isDragging }) =>
    isDragging ? 'rgba(50, 205, 50, 0.08)' : 'transparent'};

  &:hover {
    border-color: var(--accent);
    background: rgba(50, 205, 50, 0.05);
  }
`;

const UploadText = styled.p`
  color: var(--text-secondary);
  font-size: 14px;
  margin: 0;
`;

const HiddenInput = styled.input`
  display: none;
`;

interface UploadZoneProps {
  onUpload: (file: File) => void;
  uploading: boolean;
}

export function UploadZoneView({ onUpload, uploading }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) onUpload(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  return (
    <>
      <HiddenInput
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.fountain,.fdx"
        className="upload-zone-input"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(file);
        }}
      />
      <UploadZone_
        isDragging={isDragging}
        onClick={() => inputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={() => setIsDragging(false)}
        className={`upload-zone${isDragging ? ' upload-zone--dragging' : ''}`}
      >
        <UploadText className="upload-zone-text">
          {uploading
            ? 'Uploading...'
            : 'Drop .fountain / .txt / .pdf / .fdx here or click to upload — we auto-format to Fountain'}
        </UploadText>
      </UploadZone_>
    </>
  );
}
