import styled from '@emotion/styled';
import { useState } from 'react';
import { Button } from './layout.tsx';

const ModalOverlay = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
`;

const ModalContent = styled.div`
  width: 100%;
  max-width: 420px;
  background: var(--bg-surface);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  padding: 24px;
  max-height: 90vh;
  overflow-y: auto;
`;

const ModalTitle = styled.h2`
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 20px;
  color: var(--text-primary);
`;

const FormGroup = styled.div`
  margin-bottom: 14px;
`;

const Label = styled.label`
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
`;

const Input = styled.input`
  width: 100%;
  padding: 8px 12px;
  background: var(--bg-base);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  transition: border-color var(--transition);

  &:focus {
    border-color: var(--accent);
  }
`;

const ModalActions = styled.div`
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
`;

interface CreateModalProps {
  onClose: () => void;
  onCreate: (form: CreateFormData) => Promise<void>;
}

export interface CreateFormData {
  title: string;
  author: string;
  credit: string;
  source: string;
  draft_date: string;
  contact: string;
  genre: string;
}

const EMPTY_FORM: CreateFormData = {
  title: '',
  author: '',
  credit: 'Written by',
  source: '',
  draft_date: '',
  contact: '',
  genre: '',
};

export function CreateModal({ onClose, onCreate }: CreateModalProps) {
  const [form, setForm] = useState<CreateFormData>(EMPTY_FORM);
  const [creating, setCreating] = useState(false);

  const handleSubmit = async () => {
    if (!form.title.trim()) return;
    setCreating(true);
    try {
      await onCreate(form);
    } finally {
      setCreating(false);
    }
  };

  return (
    <ModalOverlay className="create-modal-overlay" onClick={onClose}>
      <ModalContent className="create-modal" onClick={(e) => e.stopPropagation()}>
        <ModalTitle className="create-modal-title">Start New Screenplay</ModalTitle>
        <FormGroup className="create-modal-field">
          <Label className="create-modal-label">Title *</Label>
          <Input
            placeholder="My Screenplay"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            className="create-modal-input"
            autoFocus
          />
        </FormGroup>
        <FormGroup className="create-modal-field">
          <Label className="create-modal-label">Credit</Label>
          <Input
            placeholder="Written by"
            value={form.credit}
            onChange={(e) => setForm({ ...form, credit: e.target.value })}
            className="create-modal-input"
          />
        </FormGroup>
        <FormGroup className="create-modal-field">
          <Label className="create-modal-label">Author</Label>
          <Input
            placeholder="Your name"
            value={form.author}
            onChange={(e) => setForm({ ...form, author: e.target.value })}
            className="create-modal-input"
          />
        </FormGroup>
        <FormGroup className="create-modal-field">
          <Label className="create-modal-label">Source</Label>
          <Input
            placeholder="Based on... (if adapted)"
            value={form.source}
            onChange={(e) => setForm({ ...form, source: e.target.value })}
            className="create-modal-input"
          />
        </FormGroup>
        <FormGroup className="create-modal-field">
          <Label className="create-modal-label">Draft Date</Label>
          <Input
            type="date"
            value={form.draft_date}
            onChange={(e) => setForm({ ...form, draft_date: e.target.value })}
            className="create-modal-input"
          />
        </FormGroup>
        <FormGroup className="create-modal-field">
          <Label className="create-modal-label">Contact</Label>
          <Input
            placeholder="Email, agency, or address"
            value={form.contact}
            onChange={(e) => setForm({ ...form, contact: e.target.value })}
            className="create-modal-input"
          />
        </FormGroup>
        <FormGroup className="create-modal-field">
          <Label className="create-modal-label">Genre</Label>
          <Input
            placeholder="Drama, Comedy, etc."
            value={form.genre}
            onChange={(e) => setForm({ ...form, genre: e.target.value })}
            className="create-modal-input"
          />
        </FormGroup>
        <ModalActions className="create-modal-actions">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            disabled={creating || !form.title.trim()}
            onClick={handleSubmit}
          >
            {creating ? 'Creating...' : 'Create'}
          </Button>
        </ModalActions>
      </ModalContent>
    </ModalOverlay>
  );
}
