import site
import os

snap_dir = os.getenv("SNAP")
snapcraft_stage_dir = os.getenv("SNAPCRAFT_STAGE")
snapcraft_part_install = os.getenv("SNAPCRAFT_PART_INSTALL")

for d in (snap_dir, snapcraft_stage_dir, snapcraft_part_install):
    if d:
        site_dir = os.path.join(d, "lib/python3.5/site-packages")
        site.addsitedir(site_dir)

if snap_dir:
    site.ENABLE_USER_SITE = False