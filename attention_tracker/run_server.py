"""
سكريبت بسيط لتشغيل خادم FastAPI بدون مشاكل colorama
"""
import os
import sys

# تعطيل colorama قبل أي استيراد آخر
os.environ['NO_COLOR'] = '1'
os.environ['TERM'] = 'dumb'

import uvicorn
from fastapi_server import app, logger

if __name__ == '__main__':
    try:
        # Ensure port 5050 is available before claiming the server is running.
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", 5050))
            s.close()
        except OSError as bind_err:
            # Port is in use — inspect the owner. Only treat this as an ERROR if it's
            # not our attention server; if it is, exit cleanly with INFO.
            try:
                import subprocess, re
                out = subprocess.check_output("netstat -ano | findstr :5050", shell=True, stderr=subprocess.STDOUT, text=True)

                # Parse PID from LISTENING line
                pid = None
                for line in out.splitlines():
                    if ':5050' in line and 'LISTEN' in line:
                        parts = re.split(r"\s+", line.strip())
                        if parts:
                            pid = parts[-1]
                            break

                if pid:
                    # Try to read the command line for the PID (WMIC or PowerShell)
                    cmdline = None
                    try:
                        cmdline = subprocess.check_output(f'wmic process where ProcessId={pid} get CommandLine /FORMAT:LIST', shell=True, stderr=subprocess.DEVNULL, text=True)
                    except Exception:
                        try:
                            pw = f"Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\" | Select-Object -ExpandProperty CommandLine"
                            cmdline = subprocess.check_output(["powershell", "-Command", pw], stderr=subprocess.DEVNULL, text=True)
                        except Exception:
                            cmdline = None

                    summary = str(cmdline or '').lower()
                    if 'fastapi_server' in summary or 'attention_tracker' in summary or 'run_server.py' in summary:
                        logger.info(f"Attention server already running (PID {pid}). Exiting without starting a new instance.")
                        sys.exit(0)
                    else:
                        logger.error("Port 5050 is already in use by a different process. netstat output follows:")
                        logger.error(out.strip())
                        logger.error(f"PID {pid} command line (truncated): {summary.strip()[:400]}")
                else:
                    logger.error("Port 5050 appears in use but PID could not be parsed. netstat output follows:")
                    logger.error(out.strip())
            except Exception:
                logger.exception('Failed to inspect existing listener on port 5050')
            sys.exit(1)

        logger.info("🚀 خادم تتبع الانتباه يبدأ الآن على http://localhost:5050")
        uvicorn.run(app, host="0.0.0.0", port=5050)
    except KeyboardInterrupt:
        logger.info("تم إيقاف الخادم")
    except Exception as e:
        logger.error(f"خطأ في تشغيل الخادم: {e}")
