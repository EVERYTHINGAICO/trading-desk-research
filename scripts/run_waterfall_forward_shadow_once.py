#!/usr/bin/env python3
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from desk.config import load_settings,project_root
from desk.db import connect,init_db
from desk.waterfall import load_config,run
def main():
 cfg,h=load_config(ROOT/'config'/'waterfall_v1.json')
 if not cfg['enabled']: print('waterfall disabled');return
 c=connect(project_root()/load_settings()['db_path']);init_db(c);print(json.dumps(run(c,cfg,h)))
if __name__=='__main__':main()
