## Steps to run as cron job

- Send command `crontab -e`
- At the ned of the file add the below command which will trigger the job every 5 min.
- `*/5 * * * * cd /home/checker && . ./venv/bin/activate && python3 status_check.py > /tmp/checker.log`
- Verify that crontab is running by `service cron status` and `crontab -l` or by checking the logs.

The above command assumes that the script is in `/home/checker` directory with `venv` as the virtual environment and all dependencies installed.

> **A SkTechHub Product**
