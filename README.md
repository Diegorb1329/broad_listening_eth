# Broad Listening ETH

This repository contains tools to extract and analyze content from any Discourse forum and GitHub repositories. Originally designed for the Ethereum community, it has been generalized to work with any Discourse forum and GitHub repository.

## Project Structure

```
broad_listening_eth/
├── Data/               # Directory for extracted data
│   ├── logs/          # Execution logs
│   └── [forum_name]/  # Forum-specific data
├── src/               # Source code
└── venv/              # Python virtual environment
```

## Discourse Forum Scraper

A generic and flexible scraper for any Discourse-based forum. It allows extracting content in an organized way while respecting server rate limits.

### Features

- Automatic Discourse forum validation
- Category extraction with statistics
- Topic extraction by category
- Complete topic content extraction (posts and replies)
- Detailed logging system
- CSV data storage
- Error handling and rate limiting
- Interactive user interface

### Usage

```bash
python src/discourse_scraper.py
```

The script will guide you through:
1. Entering the Discourse forum URL
2. Selecting categories to extract
3. Configuring the number of pages to process
4. Choosing whether to extract complete topic content

### Data Structure

Data is saved in the following structure:
```
Data/
└── [forum_name]/
    ├── categories.csv
    ├── topics/
    │   └── [category_name]_topics.csv
    └── contents/
        └── [topic_name]_posts.csv
```

## GitHub Issues Scraper

An issue and comment extractor for GitHub that allows analyzing repository discussions. Supports both JSON and SQLite storage.

### Features

- Issue extraction (open, closed, or all)
- Label filtering
- Comment extraction
- GitHub authentication token support
- API rate limit handling
- Dual storage (JSON and SQLite)
- Basic issue statistics

### Usage

```bash
# Configure GitHub token (recommended)
export GITHUB_TOKEN=your_token_here

# Run the scraper
python src/github_issues.py --owner username --repo repository [options]
```

Available options:
- `--state`: Issue state (open/closed/all)
- `--labels`: Labels to filter by
- `--max-issues`: Maximum number of issues to process
- `--db-path`: Path to SQLite database

### Data Structure

Data is saved as:
```
Data/
├── issues_[state]_[labels]_[timestamp].json
├── comments_issue_[number].json
├── issues_with_comments_[state]_[labels]_[timestamp].json
└── labels_[timestamp].json
```

## Three-Column Table (3TC) Formatter

A tool to format Discourse post data into a standardized three-column format for easier analysis and keyword searching.

### Features

- Converts multiple CSV files into a unified format
- Generates unique IDs for each conversation
- Creates metadata mapping for original sources
- Supports topic metadata integration
- Detailed logging system
- Maintains data provenance

### Usage

```bash
python src/t3c_format.py
```

The script will interactively prompt for:
1. Input directory containing CSV files
2. Optional topics metadata file
3. Output directory for formatted data
4. Custom output filename

### Data Structure

The formatter creates two files:
```
output_dir/
├── t3c_formatted.csv        # Main data in 3-column format
└── metadata_t3c_formatted.csv  # Source file mapping and metadata
```

Main data columns:
- `id`: Numerical identifier for the conversation
- `interview`: Author of the post
- `comment`: Content of the post

Metadata columns:
- `id`: Matches the main data ID
- `original_file`: Source CSV filename
- `original_title`: Original topic title
- `post_count`: Number of posts in conversation
- Additional topic metadata (if available)

## Requirements

- Python 3.6+
- Required libraries:
  ```
  requests
  beautifulsoup4
  pandas
  ```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/broad_listening_eth.git
cd broad_listening_eth
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Contributing

Contributions are welcome. Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Submit a pull request

## License

This project is under the MIT License. See the `LICENSE` file for details. 