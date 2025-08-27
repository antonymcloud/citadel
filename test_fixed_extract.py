import backup_fixed
import json

mock_output = """
Creating archive at "/home/user/backup-2025-08-27"
[WARN] ------------------------------------------------------------------------------
[WARN] Archive name: backup-2025-08-27
[WARN] Archive fingerprint: 1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
[WARN] Time (start): 2025-08-27T12:00:00.000000
[WARN] Time (end): 2025-08-27T12:05:00.000000
[WARN] Duration: 300.00 seconds
[WARN] Number of files: 1234
[WARN] Original size Compressed size Deduplicated size
[WARN] This archive: 1.00 GB 500.00 MB 200.00 MB
[WARN] All archives: 10.00 GB 5.00 GB 2.00 GB
[WARN] Unique chunks         Total size
[WARN] Chunk index: 1234     123.45 MB    100.00 KB
[WARN] ------------------------------------------------------------------------------
Finished backup
"""

stats = backup_fixed.extract_stats_from_output(mock_output)
print(json.dumps(stats, indent=2))
