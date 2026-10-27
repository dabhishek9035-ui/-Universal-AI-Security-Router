'use client';
import { THEMES } from '@/lib/themes';
import { useStore } from '@/state/store';

export default function ThemeSwitcher() {
  const themeId = useStore((s) => s.themeId);
  const setTheme = useStore((s) => s.setTheme);
  return (
    <div className="theme-switcher" role="group" aria-label="Theme">
      {Object.values(THEMES).map((t) => (
        <button key={t.id} type="button" className={t.id === themeId ? 'on' : ''} aria-pressed={t.id === themeId} aria-label={`${t.label} theme`} title={t.label}
          onClick={() => setTheme(t.id)} style={{ ['--sw1' as string]: t.scene.c2, ['--sw2' as string]: t.ui.accent }} />
      ))}
    </div>
  );
}
