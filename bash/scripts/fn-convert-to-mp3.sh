#!/bin/bash

:to-mp3() {
  cwd=$(pwd)
  input_dir="${1:-$cwd}"
  output_dir="$input_dir/convert-mp3"
  skip_confirm=false

  mkdir -p "$output_dir"

  find "$input_dir" -type f \( -iname "*.webm" -o -iname "*.mkv" \) \
    -exec bash -c 'ffmpeg -hide_banner -loglevel error -i "$0" -vn -acodec libmp3lame -q:a 0 "$1/$(basename "${0%.*}.mp3")"' {} "$output_dir" \;

  exit

  # Array of file extensions to convert
  declare -a FILE_EXTENSIONS=("webm" "mvk")

  # Optional command-line argument to override file extensions
  while [[ $# -gt 0 ]]; do
    case $1 in
      --file-extensions)
        shift
        IFS=',' read -r -a FILE_EXTENSIONS <<< "$1"
        ;;
      -y)
        shift
        skip_confirm=true
        ;;
    esac
    shift
  done

  if [ "$skip_confirm" = false ]; then
    read -p "Sure to convert files in '$input_dir'? [y/N]: " confirm

    if [[ $confirm != [Yy]* ]]; then  
      exit
    fi
  fi


  # Function to convert files based on the specified extensions
  for ext in "${FILE_EXTENSIONS[@]}"; do
    for file in $input_dir/*.$ext; do
      if [ -f "$file" ]; then
        base_name=$(basename "$file")
        new_file_name="${base_name/$ext/mp3}"
        output_path="$output_dir/$new_file_name"

        ffmpeg -i "$input_file" -vn -acodec libmp3lame -q:a 0 "$output_path"
      fi
    done
  done

  echo "Conversion completed."
}