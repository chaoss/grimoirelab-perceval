import sys

if hasattr(sys, 'gettotalrefcount'):
    from _sysconfigdata_dm import *
else:
    from _sysconfigdata_m import *
