import sys
import os
import time

# Add PothosSDR to path for DLLs
pothos_path = r"C:\Program Files\PothosSDR"
pothos_bin = os.path.join(pothos_path, "bin")
os.environ['PATH'] = pothos_bin + os.pathsep + os.environ.get('PATH', '')
if hasattr(os, 'add_dll_directory'):
    try:
        os.add_dll_directory(pothos_bin)
    except:
        pass

# Add site-packages to path
sys.path.append(r"C:\Program Files\PothosSDR\lib\site-packages")

from src.rf_analyzer.rf.soapy_wrapper import SoapySDR

def test():
    print("Initializing SoapySDR...")
    sdr = SoapySDR()
    
    print("Enumerating...")
    devs = sdr.enumerate("driver=uhd")
    print(f"Found {len(devs)} devices")
    
    if not devs:
        return
        
    args = devs[0]
    print(f"Opening device: {args}")
    
    # Construct args string for display
    args_str = ",".join([f"{k}={v}" for k,v in args.items()])
    print(f"Args string: {args_str}")
    
    try:
        # This triggers FPGA load
        print("Making device (loading FPGA)...")
        start = time.time()
        d = sdr.make_device(args)
        print(f"Device created in {time.time()-start:.2f}s!")
        
        print("Closing device...")
        sdr.unmake_device()
        print("Success!")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test()
