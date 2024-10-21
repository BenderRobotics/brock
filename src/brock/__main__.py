import os
import sys

if __name__ == '__main__':
    if __package__ == '':
        # To be able to run 'python wheel-0.9.whl/wheel':
        import os.path
        path = os.path.dirname(os.path.dirname(__file__))
        sys.path[0:0] = [path]

    import brock.cli.main

    sys.exit(brock.cli.main.main())
