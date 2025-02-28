source /opt/anaconda/etc/profile.d/conda.sh
conda activate ImagingReduction

python /SNS/VENUS/shared/software/git/venus_scripts/scripts/normalization_for_timepix.py $1 $2 $3 $4 $5 $6


# working test
# ./normalization_for_timepix.sh --sample /SNS/VENUS/IPTS-34808/shared/autoreduce/mcp/November17_Sample6_UA_H_Batteries_1_5_Angs_min_30Hz_5C --ob /SNS/VENUS/IPTS-34808/shared/autoreduce/mcp/November17_OB_for_UA_H_Batteries_1_5_Angs_min_30Hz_5C --output /SNS/VENUS/IPTS-34808/shared/processed_data/jean_testA