import type { WorkspaceArea } from './workspaceNavigation';

const items: { area: WorkspaceArea; label: string; id: string }[] = [
  { area: 'tasks', label: '任务库', id: 'tab-tasks' },
  { area: 'workbench', label: '执行工作台', id: 'tab-single' },
  { area: 'runs', label: '运行记录', id: 'tab-runs' },
  { area: 'experiments', label: '实验中心', id: 'tab-experiment' },
];

export function ProductNavigation({ active, disabled, onNavigate }: {
  active: WorkspaceArea;
  disabled: boolean;
  onNavigate: (area: WorkspaceArea) => void;
}) {
  return <nav className="workspace-navigation" aria-label="工作区导航">
    {items.map(item => <button key={item.area} id={item.id} type="button"
      className={active === item.area ? 'active' : ''} aria-pressed={active === item.area}
      disabled={disabled} onClick={() => onNavigate(item.area)}>{item.label}</button>)}
  </nav>;
}
