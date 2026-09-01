<h1 align="center">Upwork Scraper</h1>
<h2 align="center">Python + Selenium + SQLite</h2>

---

Upwork Scraper performs a single authenticated scrape of Upwork Best Matches and stores job data in SQLite. The browser remains visible so Upwork verification or two-factor authentication can be completed manually when required.

Upwork Scraper is designed to automate the process of scraping job postings from **Upwork Best Matches**. It utilizes Selenium for web scraping and interacts with the Upwork website to extract job details, including job titles, descriptions, and proposals. The script then stores the extracted data in a SQLite database for easy access and retrieval.

The script provides a streamlined solution for users who want to efficiently search for new job opportunities on Upwork without the hassle of manually browsing through job listings.

---
## Benefits

- **Time Saving:** Automates the process of scraping job postings from Upwork, saving users time and effort.
- **Efficient Job Search:** Facilitates a more efficient job search experience by automatically collecting and organizing job details.
- **Scheduler Friendly:** Each invocation performs one scrape and exits; use cron or systemd for recurring runs.

## Key Features

- **Automated Scraping:** Automatically scrolls through job postings on Upwork and extracts relevant job details.
- **Database Integration:** Stores job details in a SQLite database for easy access and retrieval.


## Disclaimer

This script is designed to automate the process of scraping job postings from Upwork in order to streamline the job searching experience. It aims to save time and effort for individuals who regularly check for new job opportunities on the site.

While the script is intended to be a helpful tool, users should be aware that scraping data from Upwork may potentially violate Upwork's terms of service or other legal agreements. It is important to use this script responsibly and in accordance with all applicable laws and regulations.

The author of this script disclaims any liability for the misuse or improper use of the script. Users assume all risks associated with its use, including any legal consequences that may arise from violating Upwork's terms of service.

By using this script, you agree to use it responsibly and to comply with all applicable laws and regulations. The author encourages users to review Upwork's terms of service and other legal agreements before using this script.

Use this script at your own discretion and risk.

## Requirements

- Python 3.11+
- Selenium
- Undetected Chromedriver
- SQLite3
- Google Chrome or Chromium

## Tested Environment

This program has been tested and verified to work correctly in Python 3.11.

## Installation with uv (recommended)

Install [uv](https://docs.astral.sh/uv/) and synchronize the locked environment:

```bash
uv sync
```

Run the scraper with:

```bash
uv run upwork-scraper
```

The legacy command remains supported:

```bash
uv run python upwork_best_matches_scraper.py
```

### Install local commit checks

Install the pre-commit hooks once per clone:

```bash
pre-commit install
```

The hooks run Ruff and Gitleaks before each commit. Gitleaks scans staged changes for
credentials and other secrets. Install Gitleaks separately and ensure it is available on
your `PATH`; the project pins the hook definition to Gitleaks `v8.30.1`.

To run all hooks manually:

```bash
pre-commit run --all-files
```

If Gitleaks reports a real secret, stop and rotate it before committing. Do not bypass the
hook unless the finding has been reviewed and is demonstrably a false positive.

## Installation with pip

1. **Create Virtual Environment:** It's recommended to create a virtual environment to isolate the dependencies of this project. You can create a virtual environment with Python 3.11 using the following command:

    ```bash
    python3 -m venv venv
    ```

    This command will create a virtual environment named `venv` in the current directory.

2. **Activate Virtual Environment:** After creating the virtual environment, activate it using the appropriate command for your operating system:

    - On Windows:

        ```bash
        .\venv\Scripts\activate
        ```

    - On macOS and Linux:

        ```bash
        source venv/bin/activate
        ```
      
3. **Clone the repository:**
   
    ```
    git clone https://github.com/roperi/UpworkScraper.git
    ```

4. **Navigate to the project directory:**
   
    ```
    cd UpworkScraper/
    ```

5. **Install the required dependencies:**
   
    ```
    pip install -r requirements.txt
    ```

## Configuration

Copy `.env.example` to `.env` and set the required credentials:

```
cp .env.example .env
```

`.env` must not be committed. For production or scheduled execution, environment variables may be supplied directly by the service manager instead.

```dotenv
UPWORK_USERNAME=your-email@example.com
UPWORK_PASSWORD=replace-me
```

**Configuration**
* `UPWORK_USERNAME` and `UPWORK_PASSWORD` are required.
* `UPWORK_USER_NAME` is optional and can contain the first name shown in the Upwork profile panel.
* `BROWSER_EXECUTABLE_PATH` is optional. Without it, Google Chrome is preferred and Chromium is used as a fallback.
* `UPWORK_PROXY_SERVER` is optional and accepts `http[s]://host:port`, `socks4://host:port`,
  `socks5://host:port`, or `host:port` (HTTP shorthand).
* `UPWORK_DATABASE_PATH`, `UPWORK_DRIVER_CACHE_DIR`, `UPWORK_BROWSER_PROFILE_DIR`,
  `UPWORK_VERIFICATION_TIMEOUT`, and `LOG_LEVEL` are optional.
* The browser profile is persistent by default, so cookies and completed Upwork
  verification can be reused on later runs. Do not use the profile directory
  concurrently from multiple scraper processes.

The browser major version is detected automatically. Users should not normally maintain a Chrome version list.

If Upwork reports network restrictions, configure the same stable proxy route that works in
your normal browser. Avoid alternating between direct access and different proxy exit IPs.
The scraper does not rotate proxies and does not accept credentials embedded in the proxy URL.

For example, an SSH SOCKS tunnel can be configured with:

```bash
ssh -N -D 1080 user@proxy-host
export UPWORK_PROXY_SERVER=socks5://127.0.0.1:1080
```

Keep the tunnel and the scraper on the same stable route for the account’s session.

Validate configuration without starting a browser login:

```bash
uv run upwork-scraper --check-config
```

Validate the live Upwork login without scraping or changing the jobs database:

```bash
uv run upwork-scraper --validate-login
```

This opens the dedicated visible browser profile and waits for any Upwork security verification
or two-factor authentication. It is a manual integration check and is not part of the automated
test suite or CI.

The CLI also supports these overrides for one run:

* `--database PATH` changes the SQLite database location.
* `--browser-path PATH` selects a specific Chrome or Chromium executable.
* `--proxy-server VALUE` overrides `UPWORK_PROXY_SERVER`.
* `--verification-timeout SECONDS` changes the manual verification window.
* `--log-level LEVEL` changes console and file logging verbosity.


## Usage

Run one scrape with the recommended command:

```bash
uv run upwork-scraper
```

The legacy entrypoint is also supported:

```bash
uv run python upwork_best_matches_scraper.py
```

## Functionality
Upwork Scraper performs the following tasks:

1. Goes to the Upwork login page and logs you in.
2. Scrapes job postings from Upwork Best Matches page.
3. Parses job details and stores them in a SQLite database.

## Automate execution of script with a Cron job

You can launch Upwork scraper via a bash script as a cron job. 

### Bash script

Create a `launch_upwork_scraper.sh` file and put it inside a `bin` folder in the project directory.

```commandline
#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
parent="$(dirname "$DIR")"

# Run one scrape
cd "$parent"
nohup uv run upwork-scraper > /dev/null 2>&1 &
```
^ Edit the paths according to your virtual environment location.

Make the bash script executable:
```commandline
chmod +x bin/launch_upwork_scraper.sh
```

### Crontab

Edit your crontab to schedule the execution of the bash script. 

In the following example the scraper will be launched every 6 hours. So it should be run at minute 0 past every 6th hour. This means that the script will be run at 12:00 AM, 6:00 AM, 12:00 PM, and 6:00 PM every day

```commandline
0 */6 * * * /path/to/your/UpworkScraper/bin/launch_upwork_scraper.sh
```

You might have to add the following variables inside your crontab in order to launch the Chromedriver. See [here](https://stackoverflow.com/questions/50117377/selenium-with-chromedriver-doesnt-start-via-cron) for more info.
```commandline
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin
DISPLAY=:0   
```

The values above are just examples. You need to replace them by finding your own values by issuing:
```
echo $SHELL
echo $PATH
env | grep "DISPLAY"
```

## Contributing
Contributions are welcome! If you encounter any issues or have suggestions for improvements, please open an issue or submit a pull request.


## Copyright and licenses
Copyright © 2026 roperi. 

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
