import os
import argparse
from re import L
import subprocess
from pathlib import Path
import csv

def convert_to_text(pdffile):
    subprocess.run(["pdftotext", "-simple2", pdffile, "buffer.txt"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if os.path.exists("buffer.txt"):
        content = Path("buffer.txt").read_text()
        os.remove("buffer.txt")
        return content.splitlines()
    else:
        return None

def get_string_from_dups(arr):
    arr_counts = {i:arr.count(i) for i in arr}
    arrstr = ""

    count = 0
    for arr_name in arr_counts.keys():
        arrstr += str(arr_counts[arr_name]) + "x " + str(arr_name)

        count += 1
        if count < len(arr_counts):
            arrstr += ","

    return arrstr

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("loc", help="Location of wipe reports", nargs=1, type=str)
    parser.add_argument("output", help="Path to output csv", nargs=1, type=str)
    args = parser.parse_args()

    output_list = []

    # generate list of all files
    wipe_dir = Path(args.loc[0])
    file_list = [f for f in wipe_dir.glob('**/*') if f.is_file()]

    for file in file_list:
        file_path = Path(file)
        extension = file_path.suffix
        name = file_path.stem

        # ignore files that are not PDFs
        if extension.lower() != ".pdf":
            continue

        # ignore erasur certificates
        if "BitRaserCertificate" in name:
            continue

        # vars to store info
        cur_model = ""
        cur_serial = ""
        cur_chassisserial = ""
        cur_disk = []
        cur_cpu = []
        cur_mem = 0
        cur_gpu = []

        file_content = convert_to_text(file)
        if file_content is None:
            continue

        for line in range(len(file_content)):
            # this is where the main parsing happens
            parts = file_content[line].split(" ")
            if line < len(file_content) - 1:
                parts_next = file_content[line + 1].split(" ")

                # skip to next page if needed
                if parts_next == ['The', 'information', 'contained', 'in', 'this', 'report', 'is', 'digitally', 'protected', 'and', 'has', 'been', 'generated', 'by', 'the', 'BitRaser', 'profiling', 'process.'] and line < len(file_content) - 5:
                    parts_next = file_content[line + 5]

            if parts[0] == "Model" and parts[1] == "Name:":
                # found model name line
                for part in parts[2:]:
                    # stop recording model after reading 'UUID'
                    if part == "UUID":
                        break
                        
                    cur_model += part

                cur_model = cur_model.split("UUID:")[0]

            if parts[0] == "System" and parts[1] == "Serial:":
                # found serial line
                cur_serial = parts[2]

            if parts[0] == "Chassis" and parts[1] == "Serial:":
                # found chassis serial
                cur_chassisserial = parts[2]

            if parts[0] == "Disk" and parts[1].isnumeric():
                # found disk
                model_index = parts.index("Model:")
                serial_index = parts.index("Serial:")
                size_index = parts.index("Size:")
                type_index = parts_next.index("Type:")
                cur_disktype = parts_next[type_index + 1].replace(",", "")
                cur_diskstr = " ".join(parts[model_index + 1:serial_index]).replace(",", "")
                cur_diskstr += " (" + cur_disktype + " - " + " ".join(parts[size_index + 1:size_index + 3]).replace(",", "") + ")"
                cur_disk.append(cur_diskstr)

            if parts[0] == "Memory" and parts[1] == "Bank":
                if not parts[3].isnumeric():
                    continue

                cur_memval = int(parts[3])
                if parts[4] == "MB,":
                    cur_memval /= 1024

                cur_mem += cur_memval

            if parts[0] == "Processor":
                if parts[1] == "Not" or parts[1] == "ID:":
                    continue

                status_index = parts.index("Status:")
                cur_cpustr = " ".join(parts[2:status_index]).replace(",", "")
                cur_cpu.append(cur_cpustr)

            if parts[0] == "Graphics" and parts[1] == "Card":
                desc_index = parts.index("Description:")
                desc_gpustr = " ".join(parts[2:desc_index]).replace(",", "")
                cur_gpu.append(desc_gpustr)

        # create csv row
        cur_csv_line = {
            "model": cur_model,
            "serial": cur_serial,
            "chassis_serial": cur_chassisserial,
            "disk": get_string_from_dups(cur_disk),
            "cpu": get_string_from_dups(cur_cpu),
            "mem": str(cur_mem),
            "gpu": get_string_from_dups(cur_gpu)
        }

        #print(cur_csv_line)
        output_list.append(cur_csv_line)

    # write to csv file
    csv_cols = ["model", "serial", "chassis_serial", "disk", "cpu", "mem", "gpu"]
    with open(args.output[0], 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_cols)
        writer.writeheader()
        for data in output_list:
            writer.writerow(data)


if __name__ == "__main__":
    main()
