import sys, os
import re
import subprocess
import glob
import logging
import argparse
from pathlib import Path

# to activate ImagingReduction
# > source /opt/anaconda/etc/profile.d/conda.sh
# > conda activate base
# > conda activate ImagingReduction

file_name, ext = os.path.splitext(os.path.basename(__file__))
log_file_name = f"/SNS/VENUS/shared/log/{file_name}.log"
logging.basicConfig(filename=log_file_name,
                    filemode='w',
                    format='[%(levelname)s] - %(asctime)s - %(message)s',
                    level=logging.INFO)
logging.info(f"*** Starting a new script {file_name} ***")

cmd = 'mcp_detector_correction.py --skipimg '

# a run folder can be named either 'Run_1234' or '..._run1234' (case-insensitive);
# both conventions have 'run' (optionally surrounded by '_') followed by the run number
RUN_FOLDER_REGEX = re.compile(r'_?run_?\d', re.IGNORECASE)


def looks_like_run_folder(name):
    """True if the folder name matches a run convention ('Run_1234' or '..._run1234')."""
    return RUN_FOLDER_REGEX.search(name) is not None

# input_folder = f"/SNS/VENUS/IPTS-33699/images/mcp/{folder_title}"
# output_folder = f"/SNS/VENUS/IPTS-33531/shared/autoreduce/mcp/"

# list_folder = glob.glob(os.path.join(input_folder, "Run_*"))
# list_folder.sort()


def that_run_has_already_been_reduced(run_number_full_path, output_folder):
    """
    this checks if any tiff are found in the output folder (created using the input path)
    if they do, just return True and None
    if they don't, return False and the full path to that output folder
    if output folder does not exists, create it !
    """
    logging.info(f"\tChecking if that run has already been reduced:")
    run_number = os.path.basename(run_number_full_path)
    logging.info(f"\t\t{run_number =}")
    folder_name = os.path.basename(os.path.dirname(run_number_full_path))
    logging.info(f"\t\t{folder_name =}")
    output_folder_name = os.path.join(output_folder, folder_name)
    if os.path.exists(output_folder_name):
        logging.info(f"\t\t{output_folder_name} does exist already - checking now that the run is there as well!")
        output_run_full_path = os.path.join(output_folder_name, run_number)
        logging.info(f"\t\t{output_run_full_path} exists?")
        if os.path.exists(output_run_full_path):
            # check that there are many tiff files there
            list_tiff_files = glob.glob(os.path.join(output_run_full_path, "*.tif*"))
            if len(list_tiff_files) > 1:
                logging.info(f"\t\tFound many tif files in that folder, it has already been reduced with success!")
                return True, None
            else:
                logging.info(f"\t\tFolder does not contain any tif files, we need to reduce that run!")
                return False, output_folder_name
        else:
            logging.info(f"{output_run_full_path} not found!")
            return False, output_folder_name
    else:
        logging.info(f"{output_folder_name} not Found!")
        return False, output_folder_name
    

def run(input_folder, output_folder_base=None, using_tpx_sub_folder=False, verbose=False):

    def vprint(msg):
        logging.info(msg)
        if verbose:
            print(f"[verbose] {msg}")

    input_folder = os.path.abspath(input_folder.rstrip("/"))
    # mcp_detector_correction.py needs a folder, not a fits image: if an image
    # was selected, use the folder that contains it
    if input_folder.lower().endswith((".fits", ".fit")):
        vprint(f"'{input_folder}' is a fits image, using its parent folder instead")
        input_folder = os.path.dirname(input_folder)
    folder_title = os.path.basename(input_folder)
    # the path always contains '/<instrument>/IPTS-####/....', regardless of
    # whether it is the /SNS or the /gpfs (physical) mount
    match = re.search(r"/([^/]+)/(IPTS-\d+)(?:/|$)", input_folder)
    if not match:
        print(f"ERROR: could not find an '<instrument>/IPTS-####' pattern in: {input_folder}")
        logging.error(f"could not find an '<instrument>/IPTS-####' pattern in: {input_folder}")
        return
    instrument = match.group(1)
    ipts_folder = match.group(2)
    if output_folder_base:
        # user-defined output location overrides the auto-derived one
        root_output_folder = os.path.abspath(output_folder_base.rstrip("/"))
    else:
        root_output_folder = f"/SNS/{instrument}/{ipts_folder}/shared/autoreduce/mcp"

    vprint(f"instrument    = {instrument}")
    vprint(f"ipts          = {ipts_folder}")
    vprint(f"input_folder  = {input_folder}")
    vprint(f"output base   = {root_output_folder}")
    if not os.path.exists(input_folder):
        print(f"WARNING: input folder does NOT exist: {input_folder}")
        logging.warning(f"input folder does NOT exist: {input_folder}")

    if looks_like_run_folder(folder_title):
        # the provided folder is itself a run -> use it directly
        vprint(f"the selected folder '{folder_title}' is a run itself - using it directly")
        list_folder = [input_folder]
        # output layout stays root/<set>/<run>, where the set is the run's parent folder
        output_folder = f"{root_output_folder}/{os.path.basename(os.path.dirname(input_folder))}"
    else:
        # the provided folder is a set -> use the run folders inside it ('Run_*' or '*_run*')
        list_folder = [f for f in glob.glob(os.path.join(input_folder, "*"))
                       if os.path.isdir(f) and looks_like_run_folder(os.path.basename(f))]
        list_folder.sort()
        output_folder = f"{root_output_folder}/{folder_title}"
        vprint(f"found {len(list_folder)} run folder(s) to consider in {input_folder}")
        if not list_folder:
            print(f"WARNING: no run folders ('Run_*' or '*_run*') found in {input_folder} - nothing to do.")
            logging.warning(f"no run folders ('Run_*' or '*_run*') found in {input_folder}")
            return

    vprint(f"output_folder = {output_folder}")

    nbr_runs_already_reduced = 0
    nbr_new_runs_reduced = 0

    for _input_folder in list_folder:

        # mcp_detector_correction.py expects a folder containing the fits/txt
        # files, not a fits image: if a fits file got selected/matched, use the
        # folder that contains it
        if _input_folder.lower().endswith((".fits", ".fit")):
            vprint(f"'{_input_folder}' is a fits image, using its parent folder instead")
            _input_folder = os.path.dirname(_input_folder)

        run_number = os.path.basename(_input_folder)
        print(f"Working with run {run_number} ...", end="")
        
        _state, _ = that_run_has_already_been_reduced(_input_folder, root_output_folder)

        if _state:
            logging.info(f"\t\tAlready been reduced!")
            logging.info(f"")
            print(" already reduce!")
            nbr_runs_already_reduced += 1
            continue
   
        if using_tpx_sub_folder:
            _input_folder = os.path.join(_input_folder, 'tpx')

        full_output_folder = os.path.join(output_folder, run_number)
        if not os.path.exists(full_output_folder):
            os.makedirs(full_output_folder)

        full_cmd = f"{cmd} {_input_folder} {full_output_folder}"
        vprint(f"full_cmd = {full_cmd}")
        print(f"working with {run_number} ....", end="")
        logging.info(f"working with {run_number}:")
        proc = subprocess.Popen(full_cmd,
                                shell=True,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True,
                                cwd=full_output_folder)
        out, err = proc.communicate()
        vprint(f"return code = {proc.returncode}")
        if out:
            vprint(f"stdout:\n{out}")
        if err:
            vprint(f"stderr:\n{err}")
        if proc.returncode != 0:
            logging.info(f"FAILED!")
            print(f" FAILED! (check log file at /SNS/VENUS/shared/log/{file_name}.log)")
            logging.info(f"{err}")
        else:
            print(f" done!")
            logging.info(f" done!")
        
        nbr_new_runs_reduced += 1   

    logging.info(f"Nbr runs process in that batch: {nbr_new_runs_reduced}")
    logging.info(f"Nbr runs already reduced: {nbr_runs_already_reduced}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Reduce all the runs from the given source folder",
                                     epilog="Example: python manual_mcp_correction /SNS/VENUS/IPTS-3333/images/mcp/all_those_folders*")
    parser.add_argument('folder', type=str, nargs='*', help='full path to folder(s) containing the Run_* runs to reduce (MCP TimePix detector only); the IPTS/instrument are derived from this /SNS/<instrument>/<ipts>/... path')
    parser.add_argument('-o', '--output', type=str, default=None, help='base folder where the reduced runs are written (layout: <output>/<set>/<run>); if not provided, defaults to /SNS/<instrument>/<ipts>/shared/autoreduce/mcp')
    parser.add_argument('--using_tpx_sub_folder', action='store_true', help="look for the runs inside a 'tpx' sub-folder of each Run_* folder (default: False)")
    parser.add_argument('-v', '--verbose', action='store_true', help='print verbose diagnostics (resolved paths, glob results, subprocess output)')
    parser.add_argument('--log', action='store_true', help='display the content of the log file once the script is done (default: False)')
    args = parser.parse_args()

    if args.verbose:
        # also echo log messages to the console
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

    list_folder_name = args.folder
    if not list_folder_name:
        print("WARNING: no folder argument provided - nothing to do.")
    for _folder_name in list_folder_name:

        print(f"Running reduction on folder: {_folder_name}")
        logging.info(f"Running reduction on folder: {_folder_name}")
        run(_folder_name, output_folder_base=args.output, using_tpx_sub_folder=args.using_tpx_sub_folder, verbose=args.verbose)

    if args.log:
        # flush any buffered log records before reading the file back
        logging.shutdown()
        print(f"\n===== Content of log file {log_file_name} =====")
        try:
            with open(log_file_name, 'r') as f:
                print(f.read())
        except OSError as e:
            print(f"ERROR: could not read log file {log_file_name}: {e}")
