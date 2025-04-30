import pandas as pd
import os
import glob
import logging
from typing import List, Dict, Any, Tuple
import re
from datetime import datetime

class ThreeColumnFormatter:
    """
    Formats discourse post data into a three-column table (3TC) format:
    - id: Numerical identifier derived from original CSV filename
    - interview: Author of the post
    - comment: Content of the post
    """
    
    def __init__(self, input_dir: str, output_dir: str, topics_file: str = None):
        """
        Initialize the formatter
        
        Args:
            input_dir: Directory containing the input CSV files
            output_dir: Directory where the output CSV will be saved
            topics_file: Optional path to the topics CSV file for metadata
        """
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.topics_file = topics_file
        self.topics_data = None
        
        if topics_file and os.path.exists(topics_file):
            try:
                self.topics_data = pd.read_csv(topics_file)
                logging.info(f"Successfully loaded topics data from {topics_file}")
            except Exception as e:
                logging.warning(f"Could not load topics file {topics_file}: {e}")
        
        # Set up logging
        log_dir = os.path.join(output_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_filename = f"t3c_formatting_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, log_filename)),
                logging.StreamHandler()
            ]
        )
    
    def extract_id_and_title(self, filename: str) -> Tuple[int, str]:
        """
        Extract a numerical ID and title from the filename.
        Returns tuple of (id, original_title)
        """
        # Remove the extension and keyword prefix if present
        base_name = os.path.splitext(filename)[0]
        if '_' in base_name:
            parts = base_name.split('_', 1)
            if len(parts) > 1:
                base_name = parts[1]
        
        # Try to find numbers in the filename
        numbers = re.findall(r'\d+', filename)
        if numbers:
            # Use the first number found
            file_id = int(numbers[0])
        else:
            # If no number found, use a hash of the filename
            file_id = abs(hash(filename)) % (10 ** 8)  # Limit to 8 digits
        
        return file_id, base_name
    
    def create_metadata(self, processed_files: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Create a metadata DataFrame mapping IDs to original files and topics
        """
        metadata_records = []
        
        for file_info in processed_files:
            metadata = {
                'id': file_info['id'],
                'original_file': file_info['filename'],
                'original_title': file_info['title'],
                'post_count': file_info['post_count']
            }
            
            # If we have topics data, try to find matching topic information
            if self.topics_data is not None:
                # Try to find matching topic by title
                title_match = self.topics_data[
                    self.topics_data['title'].str.contains(file_info['title'], case=False, na=False)
                ]
                
                if not title_match.empty:
                    topic_info = title_match.iloc[0]
                    metadata.update({
                        'topic_url': topic_info.get('url', ''),
                        'replies_count': topic_info.get('replies_count', 0),
                        'views_count': topic_info.get('views_count', 0),
                        'created_at': topic_info.get('created_at', ''),
                        'last_posted_at': topic_info.get('last_posted_at', '')
                    })
            
            metadata_records.append(metadata)
        
        return pd.DataFrame(metadata_records)
    
    def process_csv_file(self, file_path: str, file_id: int) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Process a single CSV file into 3TC format
        Returns tuple of (formatted_df, file_metadata)
        """
        try:
            # Read the CSV file
            df = pd.read_csv(file_path)
            
            # Select and rename required columns
            formatted_df = pd.DataFrame({
                'id': [file_id] * len(df),
                'interview': df['username'],
                'comment': df['content']
            })
            
            # Create file metadata
            filename = os.path.basename(file_path)
            _, title = self.extract_id_and_title(filename)
            
            file_metadata = {
                'id': file_id,
                'filename': filename,
                'title': title,
                'post_count': len(df)
            }
            
            return formatted_df, file_metadata
            
        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")
            return pd.DataFrame(), None
    
    def format_all_files(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Process all CSV files in the input directory and combine them into one DataFrame
        Returns tuple of (formatted_data, metadata)
        """
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Get all CSV files in the input directory
        csv_files = glob.glob(os.path.join(self.input_dir, '*.csv'))
        
        if not csv_files:
            logging.error(f"No CSV files found in {self.input_dir}")
            return pd.DataFrame(), pd.DataFrame()
        
        logging.info(f"Found {len(csv_files)} CSV files to process")
        
        # Process each file and collect the results
        all_data = []
        processed_files = []
        
        for file_path in csv_files:
            filename = os.path.basename(file_path)
            file_id, _ = self.extract_id_and_title(filename)
            
            logging.info(f"Processing {filename} (ID: {file_id})")
            
            df, file_metadata = self.process_csv_file(file_path, file_id)
            if not df.empty and file_metadata:
                all_data.append(df)
                processed_files.append(file_metadata)
        
        if not all_data:
            logging.error("No data was successfully processed")
            return pd.DataFrame(), pd.DataFrame()
        
        # Combine all DataFrames
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Sort by id and reset index
        combined_df = combined_df.sort_values('id').reset_index(drop=True)
        
        # Create metadata DataFrame
        metadata_df = self.create_metadata(processed_files)
        
        return combined_df, metadata_df
    
    def save_formatted_data(self, df: pd.DataFrame, metadata_df: pd.DataFrame, 
                          filename: str = 't3c_formatted.csv') -> None:
        """
        Save the formatted DataFrame and metadata to CSV files
        """
        if df.empty:
            logging.error("No data to save")
            return
        
        # Save main data
        output_path = os.path.join(self.output_dir, filename)
        metadata_path = os.path.join(self.output_dir, f"metadata_{filename}")
        
        try:
            # Save main data
            df.to_csv(output_path, index=False)
            logging.info(f"Successfully saved formatted data to {output_path}")
            logging.info(f"Total records processed: {len(df)}")
            
            # Save metadata
            metadata_df.to_csv(metadata_path, index=False)
            logging.info(f"Successfully saved metadata to {metadata_path}")
            logging.info(f"Total files processed: {len(metadata_df)}")
            
        except Exception as e:
            logging.error(f"Error saving data: {e}")


def main():
    print("\nThree-Column Table (3TC) Formatter")
    print("=" * 50)
    
    # Get input directory
    while True:
        input_dir = input("\nEnter the path to the directory containing the CSV files: ").strip()
        if os.path.isdir(input_dir):
            break
        print("Error: Directory not found. Please enter a valid directory path.")
    
    # Get topics file path
    topics_file = input("\nEnter the path to the topics CSV file (press Enter to skip): ").strip()
    if topics_file and not os.path.exists(topics_file):
        print("Warning: Topics file not found. Proceeding without topics metadata.")
        topics_file = None
    
    # Get output directory
    output_dir = input("\nEnter the path where you want to save the formatted CSV (press Enter for same as input): ").strip()
    if not output_dir:
        output_dir = input_dir
    
    # Create formatter instance
    formatter = ThreeColumnFormatter(input_dir, output_dir, topics_file)
    
    try:
        # Process all files
        print("\nProcessing files...")
        formatted_df, metadata_df = formatter.format_all_files()
        
        if not formatted_df.empty:
            # Get output filename
            default_filename = 't3c_formatted.csv'
            filename = input(f"\nEnter output filename (press Enter for '{default_filename}'): ").strip()
            if not filename:
                filename = default_filename
            
            # Add .csv extension if not present
            if not filename.endswith('.csv'):
                filename += '.csv'
            
            # Save the formatted data and metadata
            formatter.save_formatted_data(formatted_df, metadata_df, filename)
            print("\nFormatting completed successfully!")
            print(f"Main data saved as: {filename}")
            print(f"Metadata saved as: metadata_{filename}")
            
        else:
            print("\nNo data was processed. Please check the input directory and file format.")
        
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 