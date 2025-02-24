import argparse
import logging
import os
import h5py
import glob
import numpy as np
from skimage.io import imread
import numpy as np
import multiprocessing as mp 

LOG_PATH = "/SNS/VENUS/shared/log/"
LOAD_DTYPE = np.uint16

PROTON_CHARGE_TOLERANCE = 0.1

file_name, ext = os.path.splitext(os.path.basename(__file__))
log_file_name = os.path.join(LOG_PATH, f"{file_name}.log")
logging.basicConfig(filename=log_file_name,
                    filemode='w',
                    format='[%(levelname)s] - %(asctime)s - %(message)s',
                    level=logging.INFO)
logging.info(f"*** Starting a new script {file_name} ***")


class MasterDictKeys:
    frame_number = "frame_number"
    proton_charge = "proton_charge"
    matching_ob = "matching_ob"
    list_tif = "list_tif"
    data = "data"
    nexus_path = "nexus_path"
    data_path = "data_path"
    

class StatusMetadata:
    all_frame_number_found = True
    all_proton_charge_found = True


def _worker(fl):
    return (imread(fl).astype(LOAD_DTYPE)).swapaxes(0,1)


def load_data_using_multithreading(list_tif, combine_tof=False):
    with mp.Pool(processes=40) as pool:
        data = pool.map(_worker, list_tif)

    if combine_tof:
        return np.array(data).sum(axis=0)
    else:
        return np.array(data)

def retrieve_list_of_tif(folder):
    list_tif = glob.glob(os.path.join(folder, "*.tif*"))
    list_tif.sort()
    return list_tif

def normalization():
    pass


def init_master_dict(list_run_numbers):
    master_dict = {}
    for run_number in list_run_numbers:
        master_dict[run_number] = {MasterDictKeys.nexus_path: None, 
                                   MasterDictKeys.frame_number: None, 
                                   MasterDictKeys.data_path: None, 
                                   MasterDictKeys.proton_charge: None,
                                   MasterDictKeys.matching_ob: [] ,
                                   MasterDictKeys.list_tif: [], 
                                   MasterDictKeys.data: None}

    return master_dict

def retrieve_root_nexus_full_path(sample_folder):
    clean_path = os.path.abspath(sample_folder)
    if clean_path[0] == "/":
        clean_path = clean_path[1:]

    path_splitted = clean_path.split("/")
    facility = path_splitted[0]
    instrument = path_splitted[1]
    ipts = path_splitted[2]

    return f"/{facility}/{instrument}/{ipts}/nexus/"

def update_dict_with_frame_number(master_dict):
    status_all_frame_number_found = True
    for _run_number in master_dict.keys():
        _nexus_path = master_dict[_run_number][MasterDictKeys.nexus_path]
        try:
            with h5py.File(_nexus_path, 'r') as hdf5_data:
                frame_number = hdf5_data['entry']['DASlogs']['BL10:Det:PIXELMAN:ACQ:NUM']['value'][:][-1]
        except KeyError:
            frame_number = None
            status_all_frame_number_found = False
        master_dict[_run_number][MasterDictKeys.frame_number] = frame_number
    return master_dict, status_all_frame_number_found

def update_dict_with_proton_charge(master_dict):
    for _run_number in master_dict.keys():
        _nexus_path = master_dict[_run_number][MasterDictKeys.nexus_path]
        try:
            with h5py.File(_nexus_path, 'r') as hdf5_data:
                proton_charge = hdf5_data['entry'][MasterDictKeys.proton_charge][0] / 1e12
        except KeyError:
            proton_charge = None
            status_all_proton_charge_found = False
        master_dict[_run_number][MasterDictKeys.proton_charge] = proton_charge        
    return master_dict, status_all_proton_charge_found
    
def update_dict_with_list_of_images(master_dict):
    for _run_number in master_dict.keys():
        list_tif = retrieve_list_of_tif(master_dict[_run_number][MasterDictKeys.data_path])
        master_dict[_run_number][MasterDictKeys.list_tif] = list_tif
    return master_dict

def get_list_run_number(data_folder):
    list_runs = glob.glob(os.path.join(data_folder, "Run_*"))
    list_run_number = [int(os.path.basename(run).split("_")[1]) for run in list_runs]
    return list_run_number

def update_dict_with_nexus_full_path(nexus_root_path, master_dict):
    """create dict of nexus path for each run number"""
    for run_number in master_dict.keys():
        master_dict[run_number][MasterDictKeys.nexus_path] = os.path.join(nexus_root_path, f"VENUS_{run_number}.nxs.h5")
    return master_dict

def update_dict_with_data_full_path(data_root_path, master_dict):
    """create dict of data path for each run number"""
    for run_number in master_dict.keys():
        master_dict[run_number][MasterDictKeys.data_path] = os.path.join(data_root_path, f"Run_{run_number}")
    return master_dict


def create_master_dict(list_run_numbers=None, data_type="sample", data_root_path=None, status_metadata=None):
    logging.info(f"Create {data_type} master dict of runs: {list_run_numbers = }")

    # retrieve metadata for each run number
    master_dict = init_master_dict(list_run_numbers)

    logging.info(f"updating with data full path!")
    master_dict = update_dict_with_data_full_path(data_root_path, master_dict)

    logging.info(f"updating with nexus full path!")
    master_dict = update_dict_with_nexus_full_path(nexus_root_path, master_dict)

    logging.info(f"updating with frame number!")
    master_dict, all_frame_number_found = update_dict_with_frame_number(master_dict)
    if not status_metadata.all_frame_number_found:
        status_metadata.all_frame_number_found = False
    logging.info(f"{master_dict = }")

    logging.info(f"updating with proton charge!")
    master_dict, all_proton_charge_found = update_dict_with_proton_charge(master_dict)
    if not all_proton_charge_found:
        status_metadata.all_proton_charge_found = False
    logging.info(f"{master_dict = }")

    logging.info(f"updating with list of images!")
    master_dict = update_dict_with_list_of_images(master_dict)

    return master_dict, status_metadata


def combine_ob_images(ob_master_dict, ob_status_metadata):
    logging.info(f"Combining all open beam images and correcting by proton charge and frame number ...")
    full_ob_data_corrected = []

    for _ob_run_number in ob_master_dict.keys():
        logging.info(f"Combining ob# {_ob_run_number} ...")
        ob_data = ob_master_dict[_ob_run_number][MasterDictKeys.data]







        if status_metadata.all_proton_charge_found:
            proton_charge = ob_master_dict[_ob_run_number][MasterDictKeys.proton_charge]
            logging.info(f"\t -> {proton_charge = }")
        frame_number = ob_master_dict[_ob_run_number][MasterDictKeys.frame_number]
        logging.info(f"\t -> {frame_number = }")



        full_ob_data_corrected.append(ob_data / proton_charge)

    ob_data_combined = np.array(full_ob_data_corrected).mean(axis=0)

    return ob_data_combined


if __name__ == '__main__':

    # sample_master_dict = {'run_number': {'nexus_path': 'path', 'frame_number': 'value', 'proton_charge': 'value', 'matching_ob': []}}

    parser = argparse.ArgumentParser(description="Normalized Timepix data with frame number and proton charge",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument("--sample", type=str, nargs=1, help="Path to the folder containing the sample data")
    parser.add_argument("--ob", type=str, nargs=1, help="Path to the folder containing the open beam data")
    args = parser.parse_args()
    logging.info(f"{args = }")

    sample_folder = args.sample[0]
    if not os.path.exists(sample_folder):
        logging.info(f"sample folder {sample_folder} does not exist!")
        raise FileNotFoundError(f"Folder {sample_folder} does not exist!")
    else:
        logging.info(f"sample folder {sample_folder} located!")

    ob_folder = args.ob[0]
    if not os.path.exists(ob_folder):
        logging.info(f"open beam folder {ob_folder} does not exist!")
        raise FileNotFoundError(f"Folder {ob_folder} does not exist!")
    else:
        logging.info(f"open beam folder {ob_folder} located!")

    nexus_root_path = retrieve_root_nexus_full_path(sample_folder)
    logging.info(f"{nexus_root_path =}")

    # list sample and ob run numbers
    list_sample_run_numbers = get_list_run_number(sample_folder)
    logging.info(f"{list_sample_run_numbers = }")
    list_ob_run_numbers = get_list_run_number(ob_folder)
    logging.info(f"{list_ob_run_numbers = }")

    status_metadata = StatusMetadata
    sample_master_dict, status_metadata = create_master_dict(list_run_numbers=list_sample_run_numbers, 
                                                             data_type='sample', 
                                                             data_root_path=sample_folder, 
                                                             status_metadata=status_metadata)
    ob_master_dict, status_metadata = create_master_dict(list_run_numbers=list_ob_run_numbers, 
                                                         data_type='ob', 
                                                         data_root_path=ob_folder,
                                                         status_metadata=status_metadata)

    # load ob images
    for _ob_run_number in ob_master_dict.keys():
        logging.info(f"loading ob# {_ob_run_number} ... ")
        ob_master_dict[_ob_run_number][MasterDictKeys.data] = load_data_using_multithreading(ob_master_dict[_ob_run_number][MasterDictKeys.list_tif], combine_tof=False)
        logging.info(f"ob# {_ob_run_number} loaded!")
        logging.info(f"{ob_master_dict[_ob_run_number][MasterDictKeys.data].shape = }")

    # combine all ob images
    ob_data_combined = combine_ob_images(ob_master_dict, status_metadata)
    logging.info(f"{ob_data_combined.shape = }")

    for _sample_run_number in list_sample_run_numbers:
        logging.info(f"normalization of {_sample_run_number = }")

    #     sample_proton_charge = sample_master_dict[_sample_run_number]["proton_charge"]
    #     logging.info(f"\t{sample_proton_charge = }")







    normalization()

    logging.info(f"Normalization is done!")



    # sample = /SNS/VENUS/IPTS-34808/shared/autoreduce/mcp/November17_Sample6_UA_H_Batteries_1_5_Angs_min_30Hz_5C
    # ob = /SNS/VENUS/IPTS-34808/shared/autoreduce/mcp/November17_OB_for_UA_H_Batteries_1_5_Angs_min_30Hz_5C

    # full command to use to test code
    
    # source /opt/anaconda/etc/profile.d/conda.sh
    # conda activate ImagingReduction
    # > python normalization_for_timepix.py --sample /SNS/VENUS/IPTS-34808/shared/autoreduce/mcp/November17_Sample6_UA_H_Batteries_1_5_Angs_min_30Hz_5C --ob /SNS/VENUS/IPTS-34808/shared/autoreduce/mcp/November17_OB_for_UA_H_Batteries_1_5_Angs_min_30Hz_5C