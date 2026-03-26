import os
import shutil

src_dir = r"C:\Users\karti\Downloads\fineract_goldenbucks_local_plain_20260325_131326\fineract_goldenbucks_local_plain_20260325_131326"
dst_dir = r"C:\Users\karti\Downloads\test_workbench_import\fineract_goldenbucks"

if os.path.exists(dst_dir):
    shutil.rmtree(r"C:\Users\karti\Downloads\test_workbench_import")
os.makedirs(dst_dir)

dbname = "fineract_goldenbucks"

for f in os.listdir(src_dir):
    if f.endswith('.sql'):
        if not f.startswith('00') and not f.startswith('01') and not f.startswith('02'):
            new_name = f"{dbname}_{f}"
        else:
            new_name = f
            if 'ROUTINES' in f: new_name = f"{dbname}_routines.sql"
            if 'TRIGGERS' in f: new_name = f"{dbname}_triggers.sql"
            if 'CREATE' in f: new_name = f"{dbname}_create.sql"
        
        shutil.copy2(os.path.join(src_dir, f), os.path.join(dst_dir, new_name))
        
print("Successfully created renamed folder structure")
