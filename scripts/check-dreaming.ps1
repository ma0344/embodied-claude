# Quick Dreaming / STM verification (ma-home)
$ErrorActionPreference = "Stop"
$db = Join-Path $env:USERPROFILE ".claude\sociality\social.db"
if (-not (Test-Path $db)) { $db = Join-Path $env:USERPROFILE ".claude\social.db" }
Write-Host "=== dream-digest API ==="
try {
    $digest = Invoke-RestMethod "http://127.0.0.1:8090/api/v1/stm/dream-digest"
    $digest | ConvertTo-Json -Depth 4
} catch { Write-Host "API error: $_" }

Write-Host "`n=== agent_pulse.json ==="
Get-Content (Join-Path $env:USERPROFILE ".claude\presence-ui\agent_pulse.json") -Raw

Write-Host "`n=== STM counts (python) ==="
python -c @"
import sqlite3
from pathlib import Path
db = Path(r'$db')
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
for day in ('2026-06-18','2026-06-19','2026-06-20'):
    u = conn.execute('SELECT COUNT(*) c FROM stm_entries WHERE person_id=? AND local_day=? AND dreamed_at IS NULL', ('ma', day)).fetchone()['c']
    d = conn.execute('SELECT COUNT(*) c FROM stm_entries WHERE person_id=? AND local_day=? AND dreamed_at IS NOT NULL', ('ma', day)).fetchone()['c']
    print(f'{day}: undreamed={u} dreamed={d}')
print('--- recent ---')
for r in conn.execute('SELECT local_day, kind, dreamed_at IS NOT NULL as dreamed, substr(summary,1,70) s FROM stm_entries WHERE person_id=? ORDER BY created_at DESC LIMIT 12', ('ma',)):
    print(r['local_day'], r['kind'], 'dreamed' if r['dreamed'] else 'pending', r['s'])
"@
