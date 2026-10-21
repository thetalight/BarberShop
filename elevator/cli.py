from __future__ import annotations
import argparse
from . import stories
from .web import serve


def main() -> None:
    p=argparse.ArgumentParser(description='Elevator Zero local story studio')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('check')
    sub.add_parser('list')
    s=sub.add_parser('serve'); s.add_argument('--port',type=int,default=8765)
    a=p.parse_args()
    if a.command=='serve': serve(a.port)
    elif a.command=='check':
        rows=stories.read_catalog(); print(f'{len(rows)} unique stories validated')
    else:
        for row in stories.read_catalog():print(f"{row['id']} {row['status']:8} {row['title']} — {row['core_expression']}")

if __name__=='__main__': main()
