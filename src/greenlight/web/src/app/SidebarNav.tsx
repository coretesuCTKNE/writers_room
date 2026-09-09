import styled from '@emotion/styled';
import { NavLink } from 'react-router-dom';

const Sidebar = styled.nav`
  width: 56px;
  background: var(--bg-surface);
  border-right: 1px solid var(--bg-elevated);
  padding: 8px 0;
  overflow: visible;
  flex-shrink: 0;
`;

const NavItem = styled(NavLink)`
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 0;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 17px;
  transition: all var(--transition);
  border-left: 3px solid transparent;

  &:hover {
    color: var(--text-primary);
    background: var(--bg-elevated);
  }

  &.active {
    color: var(--accent);
    background: rgba(50, 205, 50, 0.08);
    border-left-color: var(--accent);
  }

  &::after {
    content: attr(data-label);
    position: absolute;
    left: calc(100% + 10px);
    top: 50%;
    transform: translateY(-50%);
    white-space: nowrap;
    background: var(--bg-elevated);
    color: var(--text-primary);
    border: 1px solid var(--bg-base);
    border-radius: var(--radius);
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 500;
    pointer-events: none;
    opacity: 0;
    transition: opacity var(--transition);
    z-index: 50;
  }

  &:hover::after {
    opacity: 1;
  }
`;

interface SidebarNavProps {
  children?: React.ReactNode;
}

export function SidebarNav({ children }: SidebarNavProps) {
  return (
    <Sidebar className="app-sidebar">
      {children}
       <NavItem to="/workspace" data-label="Workspace" aria-label="Workspace" className="app-sidebar-nav-item">📁</NavItem>
       <NavItem to="/screenplay" data-label="Screenplay" aria-label="Screenplay" className="app-sidebar-nav-item">🎬</NavItem>
       <NavItem to="/table-read" data-label="Table Read" aria-label="Table Read" className="app-sidebar-nav-item">🎙️</NavItem>
       <NavItem to="/coverage" data-label="Coverage" aria-label="Coverage" className="app-sidebar-nav-item">📋</NavItem>
       <NavItem to="/agents" data-label="Agents" aria-label="Agents" className="app-sidebar-nav-item">🤖</NavItem>
       <NavItem to="/story-ops" data-label="Story Ops" aria-label="Story Ops" className="app-sidebar-nav-item">📈</NavItem>
       <NavItem to="/cast" data-label="Cast" aria-label="Cast" className="app-sidebar-nav-item">🎭</NavItem>
       <NavItem to="/audit" data-label="Schema" aria-label="Schema" className="app-sidebar-nav-item">🗄️</NavItem>
       <NavItem to="/history" data-label="History" aria-label="History" className="app-sidebar-nav-item">📜</NavItem>
    </Sidebar>
  );
}
