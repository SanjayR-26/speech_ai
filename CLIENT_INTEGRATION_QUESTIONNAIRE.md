## Client Integration Questionnaire & Requirements (UAE)

This questionnaire is designed to gather the information needed to integrate your support-call QA analytics into your environment. It covers audio ingestion and storage, agent mapping, workflow integration models, database deployment, security/compliance (UAE PDPL), authentication, operations, and onboarding.

Please involve the relevant stakeholders: IT/Security, Telephony/Contact Center, Data, and Operations.

---

## 1) Organization & Contacts
- **Primary technical contact**: Name, role, email, phone.
- **Business owner/sponsor**: Name, role, email.
- **Vendors/Systems in scope**: PBX/CCaaS (e.g., Avaya, Cisco, Genesys, Five9), CRM (e.g., Salesforce, Dynamics), storage (e.g., NAS, S3-compatible, Object Storage), identity provider (e.g., Azure AD, Okta).

---

## 2) Audio Ingestion & Storage

### 2.1 Current Recording Sources
- Which platforms generate call recordings? (PBX/CCaaS, VoIP gateways, call recorder appliances)
- Recording format(s) and codecs (e.g., WAV PCM, MP3, Opus)? Typical size per hour?
- How are recordings currently stored and accessed (NAS/SAN, object storage, vendor portal)?

### 2.2 File Structure & Metadata
- Directory layout or object keys (by date/agent/queue)? Retention policy?
- Available metadata per call (call ID, agent ID, queue, timestamps, customer number, language)?
- How do you link recordings to the handling agent today?

### 2.3 Access Method
- Preferred access: network share (SMB/NFS), SFTP, S3-compatible API, vendor API/webhook?
- Network specifics: subnets, firewalls, proxies, required allowlists?
- Throughput expectations: daily call volume, total hours/day, ingest window (RTO)?

---

## 3) Agent Identification & Metadata Mapping
- How are agents uniquely identified (employee ID, extension, email, SSO username)?
- What lookups are needed to map call → agent (from PBX, CRM, WFM)?
- Which fields should appear in analytics (team, queue, site, campaign)? Any PII to exclude or hash?

---

## 4) Workflow Integration Models (Choose one or more)

### Option A: Direct API Upload (REST API)
- Description: Your systems upload audio files directly to our API endpoint with metadata.
- Tech Questions:
  1. What authentication method is preferred (Bearer token, API key, OAuth 2.0, mTLS certificates)?
  2. Can you handle multipart/form-data uploads up to 5GB, or do you need chunked upload support?
  3. What metadata can you provide at upload time (agent ID/name, queue, call ID, customer info)?
  4. Do you need synchronous processing confirmation or is async webhook callback acceptable?
  5. What error handling is needed (retry logic, exponential backoff, dead letter queue)?

### Option B: Pre-Signed URL Upload (Cloud Storage)
- Description: We provide pre-signed URLs for direct upload to cloud storage, then process asynchronously.
- Tech Questions:
  1. Which cloud storage is preferred (AWS S3, Azure Blob, Google Cloud Storage)?
  2. Can your system make a pre-flight API call to get upload URLs before each upload?
  3. What's the typical file size range and concurrent upload volume at peak hours?
  4. Do you need CORS support for browser-based uploads or server-to-server only?
  5. How should we handle upload notifications (callback URL, SQS/Service Bus message)?

### Option C: Batch SFTP/FTP Integration
- Description: Drop audio files and manifest (CSV/JSON) to our managed SFTP endpoint for batch processing.
- Tech Questions:
  1. What's your preferred manifest format (CSV with headers, JSON, XML) and can you provide a sample?
  2. Expected batch frequency (real-time drops, hourly, daily) and typical batch sizes?
  3. How should the manifest reference audio files (relative paths, full paths, just filenames)?
  4. Do you need separate folders for pending/processed/error states?
  5. What notification method for batch completion (email, webhook, file marker)?

### Option D: Streaming Integration (WebSocket/SSE)
- Description: Real-time streaming of audio or transcription events for immediate processing.
- Tech Questions:
  1. Can you stream audio in real-time or only post-call completion?
  2. What audio codec/format can you stream (PCM, Opus, MP3) and sample rate?
  3. Do you need bi-directional communication or just client->server streaming?
  4. What's your reconnection strategy and state management approach?
  5. Can you handle backpressure if processing lags behind streaming rate?

### Option E: Message Queue Integration (Pub/Sub)
- Description: Publish recording URLs/metadata to message queue; we consume and process asynchronously.
- Tech Questions:
  1. Which message broker (Kafka, RabbitMQ, AWS SQS/SNS, Azure Service Bus, Google Pub/Sub)?
  2. Message format preference (JSON, Avro, Protobuf) and schema versioning approach?
  3. Do you need guaranteed delivery (at-least-once) or is at-most-once acceptable?
  4. What's the expected message volume and size limits per message?
  5. How should we acknowledge successful processing (message deletion, separate status queue)?

### Option F: Telephony Platform Direct Integration
- Description: Direct API integration with your PBX/CCaaS platform to pull recordings.
- Tech Questions:
  1. Which platform and version (Avaya, Cisco, Genesys, Five9, Talkdesk, custom)?
  2. What API scopes/permissions can you provide (recordings, metadata, agent directory)?
  3. Are there rate limits or API quotas we should be aware of?
  4. Can the platform send webhooks/notifications when calls complete?
  5. How far back can we retrieve historical recordings via API?

### Option G: Database Integration (CDC/ETL)
- Description: Read recording metadata from your database; fetch audio from referenced locations.
- Tech Questions:
  1. Database type (PostgreSQL, MySQL, Oracle, SQL Server) and can you provide read-only access?
  2. Do you support Change Data Capture (CDC) or do we need to poll for changes?
  3. What's the schema for call records and how are audio file locations stored?
  4. Network access method (direct connection, VPN, SSH tunnel, private link)?
  5. How do you handle audio file cleanup/archival and metadata retention?

### Option H: Hybrid On-Premise Agent
- Description: Deploy our containerized agent in your environment to process locally and sync results.
- Tech Questions:
  1. Container orchestration platform (Kubernetes, Docker Swarm, OpenShift, standalone Docker)?
  2. Can the agent access audio storage directly (mounted volumes, network shares, S3 API)?
  3. Outbound connectivity for results sync (HTTPS only, specific ports, proxy requirements)?
  4. Resource allocation available (CPU cores, RAM, GPU for faster processing)?
  5. How should the agent handle buffering during network outages?

---

## 5) Application Hosting Models (Choose one)

### Option A: Fully Cloud SaaS (Multi-tenant)
- Description: Application hosted in our cloud infrastructure, shared resources with data isolation.
- Tech Questions:
  1. Is multi-tenant SaaS acceptable or do you require single-tenant isolation?
  2. Which cloud regions are acceptable (UAE North/Central, Bahrain, others)?
  3. Do you need a dedicated subdomain or custom domain with SSL certificate?
  4. Required uptime SLA (99.9%, 99.95%, 99.99%) and support response times?
  5. Do you need data processing to remain in specific geographic regions?
  6. Can we use shared compute resources or do you need dedicated instances?

### Option B: Dedicated Cloud Instance (Single-tenant)
- Description: Isolated cloud deployment in your preferred region with dedicated resources.
- Tech Questions:
  1. Preferred cloud provider (AWS, Azure, GCP, Oracle Cloud)?
  2. Do you have an existing cloud account we should deploy into?
  3. Required instance types/sizes for web servers and processing workers?
  4. Auto-scaling requirements (min/max instances, scaling triggers)?
  5. Do you need multi-AZ deployment for high availability?
  6. VPN or Direct Connect requirements to your network?

### Option C: On-Premise Installation
- Description: Complete deployment within your data center on your hardware.
- Tech Questions:
  1. Server specifications available (CPU, RAM, storage, GPU for ML processing)?
  2. Operating system preference (Ubuntu 20.04/22.04, RHEL 8/9, Windows Server)?
  3. Container runtime available (Docker, Podman, containerd)?
  4. Load balancer availability (F5, HAProxy, NGINX)?
  5. SSL certificate management (Let's Encrypt, internal CA, commercial certs)?
  6. Internet connectivity for external API calls (AssemblyAI, OpenAI) or air-gapped?

### Option D: Hybrid Cloud-On Premise
- Description: Web interface in cloud, processing engines on-premise for data sovereignty.
- Tech Questions:
  1. Which components must remain on-premise (audio storage, processing, database)?
  2. Acceptable latency between cloud UI and on-premise backend?
  3. Site-to-site VPN or ExpressRoute/Direct Connect available?
  4. Can on-premise components make outbound HTTPS calls?
  5. Failover strategy if connectivity is lost?
  6. How should user authentication work across environments?

### Option E: Private Cloud (OpenStack/VMware)
- Description: Deploy on your private cloud infrastructure.
- Tech Questions:
  1. Private cloud platform (OpenStack, VMware vSphere, Nutanix)?
  2. Available compute resources and quotas?
  3. Object storage available (Swift, S3-compatible)?
  4. Network isolation requirements (VLANs, security groups)?
  5. Backup infrastructure integration requirements?
  6. Monitoring/logging integration with existing tools?

---

## 6) Database Deployment Models (Choose one)

### Option A: Managed Cloud Database Service
- Description: Fully managed database in cloud (RDS, Azure Database, Cloud SQL).
- Tech Questions:
  1. Preferred database engine (PostgreSQL 14+, MySQL 8+, SQL Server)?
  2. Required size (storage, IOPS, memory) based on retention needs?
  3. High availability requirements (Multi-AZ, read replicas, failover time)?
  4. Backup frequency and retention (point-in-time recovery needs)?
  5. Encryption requirements (at-rest, in-transit, key management)?
  6. Do you need cross-region replication for disaster recovery?

### Option B: Self-Managed Cloud Database
- Description: Database on cloud VMs that you manage directly.
- Tech Questions:
  1. Preferred instance types for database servers?
  2. Do you have DBAs to manage patching, backups, and optimization?
  3. Clustering solution preference (Patroni, Galera, Always On)?
  4. Shared storage requirements (EBS, Azure Disks, persistent disks)?
  5. Monitoring tools (CloudWatch, Datadog, Prometheus)?
  6. How will you handle database version upgrades?

### Option C: On-Premise Database Server
- Description: Database runs on your physical servers or VMs.
- Tech Questions:
  1. Existing database infrastructure to leverage or new deployment?
  2. Hardware specifications (CPU, RAM, SSD/NVMe storage)?
  3. Backup solution (Veeam, Commvault, native tools)?
  4. High availability method (clustering, replication, shared storage)?
  5. Can applications connect directly or through connection pooler?
  6. Database maintenance windows and change control process?

### Option D: Containerized Database
- Description: Database runs in containers with persistent volumes.
- Tech Questions:
  1. Container orchestration platform for stateful workloads?
  2. Persistent volume solution (local volumes, NFS, Ceph, GlusterFS)?
  3. Database operator preferences (CloudNativePG, Percona operators)?
  4. Backup strategy for containerized databases?
  5. How do you handle storage performance requirements?
  6. StatefulSet management and upgrade strategies?

### Option E: Database as a Service (Your Infrastructure)
- Description: Managed database service on your infrastructure (e.g., RDS Outposts).
- Tech Questions:
  1. Which DBaaS platform (AWS Outposts, Azure Arc, Google Anthos)?
  2. Available hardware for database nodes?
  3. Management plane connectivity requirements?
  4. Automated backup destination (local or cloud)?
  5. Compliance requirements for data at rest?
  6. Integration with existing monitoring/alerting systems?

---

## 7) Data Storage & Retention

### 7.1 Audio File Management
- How long should we retain original audio files?
- Do you need audio files accessible via API after processing?
- Archival requirements (cold storage, compression)?
- Can audio files be deleted after transcription or must they be retained?
- Do you need audio redaction capabilities (remove sensitive segments)?

### 7.2 Transcription & Results Storage
- Retention period for transcriptions and QA results?
- Do you need versioning for corrected transcripts?
- Data purge requirements (hard delete vs soft delete)?
- Export requirements before deletion?
- Legal hold or compliance retention overrides?

### 7.3 Data Residency & Compliance
- Must all data remain within UAE borders?
- Can we use UAE-region cloud services (AWS ME-South-1, Azure UAE)?
- Specific regulatory requirements (TDRA, Banking, Healthcare)?
- Data classification levels and handling requirements?
- Cross-border data transfer restrictions?

---

## 8) Security & Compliance Requirements

### 8.1 Encryption Standards
- Minimum TLS version for API communications (1.2, 1.3)?
- At-rest encryption requirements (AES-256, customer-managed keys)?
- Do you require client-side encryption before upload?
- Certificate pinning or specific CA requirements?
- Key rotation frequency and procedures?

### 8.2 Access Control & Audit
- Service account management requirements?
- API access logging and retention period?
- Do you need detailed audit trails for all data access?
- PII handling and masking requirements?
- Do you require SOC2/ISO27001 compliance evidence?

### 8.3 UAE PDPL Compliance
- Data subject rights procedures (access, deletion, portability)?
- Consent management for recording processing?
- Data breach notification requirements and timelines?
- Do you have a DPO we should coordinate with?
- Privacy impact assessment requirements?

