"""TaskGraph v0.1 executable entry point."""
from pathlib import Path
import argparse,sys,traceback
ROOT=Path(__file__).resolve().parents[2]
for folder in sorted((ROOT/"Implementation").glob("ENG-*_Engine/Source")):sys.path.insert(0,str(folder))
sys.path.insert(0,str(Path(__file__).resolve().parent));sys.path.insert(0,str(ROOT/"App"))
from startup import StartupFailure,create_runtime
from validation import validate_runtime,validation_passed
def main():
    parser=argparse.ArgumentParser(description="TaskGraph v0.1 Core Platform");parser.add_argument("--validate-only",action="store_true");args=parser.parse_args()
    try:
        runtime=create_runtime();checks=validate_runtime(runtime)
        if args.validate_only:
            for check in checks:print(("PASS" if check.passed else "FAIL"),check.name,"-",check.detail)
            from shutdown import shutdown_runtime
            shutdown=shutdown_runtime(runtime,"m1-validation-shutdown")
            shutdown_ok=all(value.status.value=="succeeded" for value in shutdown.values())
            for name,value in shutdown.items():print(("PASS" if value.status.value=="succeeded" else "FAIL"),f"Shutdown {name}","-",value.state.value)
            return 0 if validation_passed(checks) and shutdown_ok else 1
        from desktop import TaskGraphApp
        TaskGraphApp(runtime,checks,ROOT).run();return 0
    except StartupFailure as exc:
        print(f"STARTUP FAILED [{exc.stage}]",file=sys.stderr)
        for error in getattr(exc.response,"errors",()):print(f"{error.code}: {error.message}",file=sys.stderr)
        return 1
    except Exception:
        traceback.print_exc();return 1
if __name__=="__main__":raise SystemExit(main())
