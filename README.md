# Email Automation Admin UI

A Flask-based web interface for monitoring and controlling the Microsoft 365 Email Automation System.

## Overview

This admin UI provides operational control over the email automation system with:

- **Dashboard**: System overview and metrics
- **Recipients Management**: View all recipients and their email sequence status
- **Add Recipients**: Safe form to add new recipients to sequences
- **System Controls**: Manual controls for scheduler and reply detection

## Features

### Zero Ambiguity Email Status
- Clear "Sent"/"Not Sent" status for each email step
- "Yes"/"No" reply indicators
- Human-readable current status for each recipient

### Database-Driven
- All data comes from the existing email automation database
- Real-time status calculations
- No mock data or hardcoded examples

### Operational Safety
- CSRF protection on all forms
- Input validation and sanitization
- Rate limiting on form submissions
- Confirmation dialogs for destructive actions

### Simple Technology Stack
- Flask backend with Jinja2 templating
- Server-side rendering only
- Minimal CSS styling
- No JavaScript frameworks or SPA behavior

## Installation

### Prerequisites

- Python 3.8 or higher
- Access to the existing email automation system database
- Network access to the email automation backend (for system controls)

### Setup

1. **Install dependencies:**
   ```bash
   cd ui
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run the application:**
   ```bash
   python run.py
   ```

   Or for development:
   ```bash
   python app.py
   ```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

#### Basic Configuration
- `UI_PORT`: Web server port (default: 5000)
- `UI_DEBUG`: Debug mode (default: false)
- `UI_SECRET_KEY`: Secret key for sessions and CSRF

#### Database
- `DATABASE_URL`: Database connection (should match main system)

#### Security (Production)
- `UI_REQUIRE_AUTH`: Enable authentication (default: false)
- `UI_AUTH_USERNAME`: Admin username
- `UI_AUTH_PASSWORD`: Admin password
- `UI_USE_HTTPS`: Enable HTTPS (default: false)
- `UI_SSL_CERT_PATH`: SSL certificate path
- `UI_SSL_KEY_PATH`: SSL private key path

### Production Deployment

For production deployment:

1. **Set secure configuration:**
   ```bash
   UI_DEBUG=false
   UI_SECRET_KEY=your-secure-random-key
   UI_REQUIRE_AUTH=true
   UI_AUTH_PASSWORD=your-secure-password
   UI_USE_HTTPS=true
   ```

2. **Generate secret key:**
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Configure SSL certificates:**
   - Obtain SSL certificate and private key
   - Set `UI_SSL_CERT_PATH` and `UI_SSL_KEY_PATH`

4. **Network security:**
   - Configure firewall rules
   - Consider reverse proxy (nginx, apache)
   - Set `UI_ALLOWED_HOSTS` if needed

## Usage

### Dashboard
- Access at `http://localhost:5000/`
- View system metrics and status
- Quick navigation to other sections

### Recipients Management
- View all recipients: `/recipients`
- Add new recipient: `/recipients/new`
- See exact email sending status for each recipient

### System Controls
- Access controls: `/control`
- Start/stop email scheduler
- Trigger manual email processing
- Run reply detection

## Integration with Main System

The admin UI integrates with the existing email automation system by:

1. **Database Access**: Reads from the same SQLite database
2. **Backend Integration**: Calls existing scheduler and reply tracker functions
3. **No Duplication**: Uses existing business logic without reimplementation

### Database Schema

The UI expects these tables from the main system:

```sql
-- Recipients table
CREATE TABLE recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Email sequence table
CREATE TABLE email_sequence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER NOT NULL,
    step INTEGER NOT NULL CHECK (step IN (1, 2, 3)),
    scheduled_at TIMESTAMP NOT NULL,
    sent_at TIMESTAMP NULL,
    message_id TEXT NULL,
    replied BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recipient_id) REFERENCES recipients (id)
);
```

## Security

### Built-in Security Features

- **CSRF Protection**: All forms protected against cross-site request forgery
- **Input Validation**: Server-side validation of all user inputs
- **XSS Prevention**: Automatic escaping of user content
- **Rate Limiting**: Prevents form submission abuse
- **SQL Injection Prevention**: Parameterized queries only

### Security Recommendations

1. **Internal Use Only**: Deploy behind corporate firewall
2. **Authentication**: Enable `UI_REQUIRE_AUTH` for any external access
3. **HTTPS**: Always use HTTPS in production (`UI_USE_HTTPS=true`)
4. **Strong Passwords**: Use secure passwords and secret keys
5. **Regular Updates**: Keep dependencies updated
6. **Monitoring**: Monitor logs for security events

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Verify `DATABASE_URL` matches main system
   - Ensure database file exists and is accessible
   - Check file permissions

2. **Backend Integration Errors**
   - Ensure main email automation system is properly installed
   - Check Python path includes email automation modules
   - Verify configuration matches main system

3. **Permission Errors**
   - Check file system permissions
   - Ensure write access to log files
   - Verify SSL certificate permissions

4. **Port Conflicts**
   - Change `UI_PORT` if 5000 is in use
   - Check for other services on the same port

### Logging

Logs are written to:
- Console output (stdout)
- Log file specified by `UI_LOG_FILE` (default: `admin_ui.log`)

Set `UI_LOG_LEVEL=DEBUG` for detailed troubleshooting.

## Development

### Project Structure

```
ui/
├── app.py                 # Flask application factory
├── run.py                 # Production entry point
├── config.py              # Configuration management
├── database.py            # Database integration layer
├── security.py            # Security utilities
├── backend_integration.py # Backend system integration
├── routes/
│   ├── dashboard.py       # Dashboard routes
│   ├── recipients.py      # Recipients management
│   └── control.py         # System controls
├── templates/
│   ├── base.html          # Base template
│   ├── dashboard.html     # Dashboard page
│   ├── recipients.html    # Recipients table
│   ├── add_recipient.html # Add recipient form
│   └── control.html       # Control panel
├── static/
│   └── style.css          # CSS styling
├── requirements.txt       # Python dependencies
├── .env.example          # Environment configuration template
└── README.md             # This file
```

### Adding Features

1. **New Routes**: Add to appropriate route module in `routes/`
2. **New Templates**: Create in `templates/` extending `base.html`
3. **Database Queries**: Add to `database.py` with proper error handling
4. **Security**: Use decorators from `security.py` for form handling

### Testing

Run the application in debug mode:
```bash
UI_DEBUG=true python app.py
```

For production testing:
```bash
UI_DEBUG=false python run.py
```

## License

Internal use only - part of the Microsoft 365 Email Automation System.