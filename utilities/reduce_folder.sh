source /opt/anaconda/etc/profile.d/conda.sh
conda activate ImagingReduction

ipts=$1
folder_name=$2

python /SNS/VENUS/shared/software/code/automate_mcp_correction.py $ipts $folder_name