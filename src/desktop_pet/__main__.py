"""Support source and frozen ``python -m desktop_pet`` startup."""

from desktop_pet.app import main

if __name__ == "__main__":
    raise SystemExit(main())
