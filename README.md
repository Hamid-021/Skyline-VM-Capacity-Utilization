## Skyline Dashboard: VM Resource Utilization Metrics Rendering from the Visualization Page

### Step 1: Download the Python Files

1. Navigate to the directory:
   ```sh
   cd /etc/skyline
   ```
2. Download the Python files to this location and run the code to ensure it works.

   **Testing Purpose:**

   - Create a `cloud.yaml` file.
   - Add the following content to the file:
     ```yaml
     clouds:
       mycloud:
         auth:
           auth_url: http://[IP_ADDRESS]:5000/v3
           username: admin
           password: [PASSWORD]
           project_name: admin
           user_domain_name: Default
           project_domain_name: Default
         region_name: RegionOne
         interface: public
         identity_api_version: 3
     ```
   - Save the file and export the environment variable using the command:
     ```sh
     export OS_CLIENT_CONFIG_FILE=/etc/skyline/cloud.yaml
     ```
   - Run the code:
     ```sh
     python3 app.py
     ```
   - If it works, proceed to the next step to create a new systemd service.

### Step 2: Create a Systemd Service

1. Create a new systemd service file at `/etc/systemd/system/skyline-utilization.service`:

   ```ini
   [Unit]
   Description=Skyline Utilization

   [Service]
   Type=simple
   WorkingDirectory=/etc/skyline
   Environment="OS_CLIENT_CONFIG_FILE=/etc/skyline/cloud.yaml"
   ExecStart=/usr/bin/python3 app.py
   LimitNOFILE=32768

   [Install]
   WantedBy=multi-user.target
   ```

2. Enable, start, and check the status of the service:
   ```sh
   systemctl enable skyline-utilization.service
   systemctl start skyline-utilization.service
   systemctl status skyline-utilization.service
   ```

3. Browse the URL:
   ```
   http://[IP_ADDRESS]:8000/metrics
   ```
   **Expected Output:**  
   ![image](https://github.com/user-attachments/assets/2980b5de-912d-4c12-bae7-e2678eabb7c3)

### Step 3: Configure the Frontend

#### Nginx Configuration

1. Navigate to `/etc/nginx/` and add the following lines to expose the Skyline API:

   ```nginx
   location /api/metrics/ {
       proxy_pass http://[IP_ADDRESS]:8000/metrics/;  # Add trailing slash
       proxy_redirect http://[IP_ADDRESS]:8000/metrics/ /api/metrics/;
       proxy_buffering off;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       proxy_set_header X-Forwarded-Host $host;
       proxy_set_header Host [IP_ADDRESS]:8000;
   }
   ```

2. Restart the Nginx service:
   ```sh
   systemctl restart nginx
   ```
3. Browse the API URL:
   ```
   http://[IP_ADDRESS]:9999/api/metrics/[INSTANCE_ID]
   ```
   - The backend code retrieves VM metrics such as CPU, Memory, Disk I/O, and Network Traffic.
   - To apply a time interval filter, use:
     ```
     http://[IP_ADDRESS]:9999/api/metrics/[INSTANCE_ID]?timeInterval=[INTERVAL]
     ```
     **Available Intervals:** `1min, 5min, 15min, 30min, 1hour`
   
   ![image](https://github.com/user-attachments/assets/beb19b94-5069-4c7c-9125-44c121e18b4f)

#### Modify the Skyline Console

1. Navigate to:
   ```sh
   cd skyline-console/src/pages/compute/containers/Instance/Detail/
   ```
2. Edit `index.jsx` and add a **Utilization** tab:
   ```jsx
   get tabs() {
       const tabs = [
           {
               title: t('Detail'),
               key: 'detail',
               component: BaseDetail,
           },
           {
               title: t('Utilization'),
               key: 'utilization',
               component: Util,
           },
           {
               title: t('Instance Snapshots'),
               key: 'snapshots',
               component: Snapshots,
           },
       ];
   }
   ```
3. Save the file.
4. Create a new folder:
   ```sh
   mkdir skyline-console/src/pages/compute/containers/Instance/Detail/Utilization
   ```
5. Download `index.jsx` into the `Utilization` folder.

### Step 4: Precompile the Code

1. Install necessary dependencies:
   ```sh
   cd skyline-console
   yarn add @ant-design/plots@1.0.0 @ant-design/charts@1.0.0
   ```
2. Compile the code:
   ```sh
   make package
   ```
3. Install the updated package:
   ```sh
   pip3 install --force-reinstall dist/skyline_console-*.whl
   ```
4. Restart the Skyline API server and Nginx service:
   ```sh
   systemctl restart skyline-apiserver nginx
   ```

### Final Output

![image](https://github.com/user-attachments/assets/60a8d913-de82-4be6-af03-adc54f1b9d4e)

Backend and frontend phases are now complete!
