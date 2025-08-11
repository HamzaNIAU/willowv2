# YouTube OAuth Setup Guide for Suna

## OAuth Redirect URI
The redirect URI you need to add in Google Developer Console is:
```
http://localhost:8000/api/youtube/auth/callback
```

For production, replace `localhost:8000` with your actual domain:
```
https://your-domain.com/api/youtube/auth/callback
```

## Google Developer Console Setup

### 1. Create OAuth 2.0 Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **YouTube Data API v3**:
   - Go to "APIs & Services" > "Library"
   - Search for "YouTube Data API v3"
   - Click on it and press "Enable"

### 2. Create OAuth 2.0 Client ID

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. If prompted, configure the OAuth consent screen first:
   - **Application name**: Enter YOUR app name (e.g., "Suna", "Your App Name")
   - **NOT "Composio"** - this is what's showing in your consent screen
   - Add your support email
   - Add authorized domains if needed
4. For Application type, select **"Web application"**
5. Add the following:
   - **Name**: Your app name (e.g., "Suna YouTube Integration")
   - **Authorized redirect URIs**: 
     - `http://localhost:8000/api/youtube/auth/callback` (for development)
     - Add your production URL if deploying

### 3. Download Credentials

1. Once created, download the JSON credentials
2. Extract the `client_id` and `client_secret`

### 4. Configure Environment Variables

Add these to your `.env` file in the backend directory:

```bash
# YouTube OAuth Configuration
YOUTUBE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET=your_client_secret_here
YOUTUBE_REDIRECT_URI=http://localhost:8000/api/youtube/auth/callback
```

For production:
```bash
YOUTUBE_REDIRECT_URI=https://your-domain.com/api/youtube/auth/callback
```

## OAuth Consent Screen Configuration

### Why it shows "Composio"
The text "to continue to Composio" appears because either:
1. The OAuth app in Google Console is named "Composio"
2. The OAuth consent screen has "Composio" as the application name

### To Fix the Branding:

1. Go to "APIs & Services" > "OAuth consent screen"
2. Click "Edit App"
3. Update these fields:
   - **App name**: Change from "Composio" to your app name
   - **User support email**: Your support email
   - **App logo**: Upload your app logo (optional)
   - **Application home page**: Your app URL
   - **Application privacy policy link**: Your privacy policy URL
   - **Application terms of service link**: Your terms URL
4. Save the changes

### OAuth Scopes Required

The YouTube integration requests these scopes:
- `youtube.upload` - Upload videos
- `youtube.readonly` - Read channel info
- `yt-analytics.readonly` - View analytics
- `yt-analytics-monetary.readonly` - View monetization data
- `youtube.force-ssl` - Manage channel
- `youtubepartner` - YouTube Partner features
- `youtube.channel-memberships.creator` - Channel memberships

## Testing the Integration

1. Start your backend server:
   ```bash
   cd backend
   uvicorn api:app --reload --host 0.0.0.0 --port 8000
   ```

2. In the chat, type: "Can you help me setup my YouTube"

3. The agent should show a "Sign in to YouTube" button

4. Click the button to authenticate

5. After successful authentication, you can upload videos

## Troubleshooting

### "YouTube OAuth is not configured" error
- Ensure `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET` are set in `.env`
- Restart the backend server after adding environment variables

### "Invalid redirect URI" error
- Make sure the redirect URI in Google Console exactly matches what's in your `.env`
- Include the protocol (`http://` or `https://`)
- Include the port for localhost (`:8000`)

### Still shows "Composio" in consent screen
- Changes to OAuth consent screen can take a few minutes to propagate
- Try clearing browser cache or using incognito mode
- Ensure you saved the changes in Google Console

## Production Deployment

When deploying to production:

1. Update the redirect URI in both:
   - Google Console (add new authorized redirect URI)
   - Your production `.env` file

2. Consider using environment-specific configurations:
   ```bash
   # Production
   YOUTUBE_REDIRECT_URI=https://api.yourapp.com/api/youtube/auth/callback
   ```

3. Ensure HTTPS is used in production for security

## Security Notes

- Never commit `YOUTUBE_CLIENT_SECRET` to version control
- Use environment variables or secrets management
- In production, always use HTTPS for redirect URIs
- Consider implementing state parameter for CSRF protection