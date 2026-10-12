import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tts.cli import main  # noqa: E402

sys.exit(main())
