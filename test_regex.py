import re

source = 'fineract_rkp'
target = 'tgt_db'

bad_sqls = [
    'USE fineract_rkp;',
    'USE ineract_rkp;',
    'CREATE DATABASE fineract_rkp;',
    'CREATE DATABASE IF NOT EXISTS ineract_rkp;',
    'CREATE DATABASE IF NOT EXISTS fineract_rkp  ;',
    '-- A comment about fineract_rkp',
    'INSERT INTO my_table (notes) VALUES (''User fineract_rkp was here'');',
    'CREATE TABLE abstract_fineract_rkp_logs (id int);',
    'GRANT ALL PRIVILEGES ON fineract_rkp.* TO user;'
]

pat_use = re.compile(rf'(?i)(USE\s+){re.escape(source)}(\s*;)')
pat_create = re.compile(rf'(?i)(CREATE\s+DATABASE(?:\s+IF\s+NOT\s+EXISTS)?\s+){re.escape(source)}(\s*;|\s+)')

for sql in bad_sqls:
    res = sql.replace(f'\{source}\', f'\{target}\').replace(f'\"{source}\"', f'\"{target}\"').replace(f'\'{source}\'', f'\'{target}\'')
    res = pat_use.sub(rf'\g<1>{target}\g<2>', res)
    res = pat_create.sub(rf'\g<1>{target}\g<2>', res)
    print(f'IN:  {sql}\nOUT: {res}\n')
