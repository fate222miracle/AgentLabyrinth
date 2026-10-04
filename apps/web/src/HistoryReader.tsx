interface Props {
  kind: 'episode' | 'exp';
  value: string;
  busy: boolean;
  onChange: (value: string) => void;
  onRead: (value: string) => Promise<void>;
}

/** A labelled, keyboard-friendly entry to the existing read-only history handlers. */
export function HistoryReader({ kind, value, busy, onChange, onRead }: Props) {
  const inputId = kind === 'episode' ? 'input-episode-id' : 'input-exp-id';
  return (
    <form className="history-reader" onSubmit={(event) => {
      event.preventDefault();
      if (!busy && value.trim()) void onRead(value);
    }}>
      <label htmlFor={inputId}>历史 {kind === 'episode' ? 'Episode' : 'Experiment'} ID</label>
      <div className="persistence-input-row">
        <input id={inputId} className="form-input persistence-input" type="text"
          placeholder="粘贴完整 UUID" value={value} autoComplete="off" spellCheck={false}
          onChange={(event) => onChange(event.target.value)} />
        <button id={kind === 'episode' ? 'btn-load-id' : 'btn-load-exp-id'}
          className="btn-secondary" type="submit" disabled={busy || !value.trim()}>
          读取结果
        </button>
      </div>
    </form>
  );
}
