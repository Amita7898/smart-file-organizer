# Synthetic demonstration

Create a new empty folder outside your personal files. Add a small `sample.txt`, `picture.jpg` and a folder `Documents` containing a different `sample.txt`. Use clearly synthetic text contents.

1. Select the incoming `sample.txt` in Manual Mode. Verify the collision is skipped and both contents remain unchanged.
2. Select `picture.jpg`. Verify it moves to Images, then use Undo and verify it returns.
3. Add the disposable folder in Auto Mode; observe category creation and skipped collisions. Stop before undoing.
4. Capture only the app window and synthetic fixtures. Never include personal paths or file contents.

`main-window.jpg` is a capture of the rebuilt application running on macOS, not an illustration. Automated GUI tests verify the same manual, collision and automatic workflows with generated temporary fixtures.
