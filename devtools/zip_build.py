import shutil

from fusion_analysis.__version__ import VERSION

output_filename = f"dist/fusion-analysis_v{VERSION}"
dir_name = "dist/fusion-analysis"

shutil.make_archive(output_filename, "zip", dir_name)
