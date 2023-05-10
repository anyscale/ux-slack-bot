# Development
- The necessary tokens (`SLACK_BOT_OAUTH_TOKEN`, `AIRTABLE_API_KEY`) should have been baked into [the cluster env](https://console.anyscale.com/o/anyscale-internal/configurations/app-config-versions/apt_rjkfpv6lbcl3e6gdttjijsrh9q).
- When developing, run `./ngrok http 8000` to obtain a url to use as the _Request URL_ on [this page](https://api.slack.com/apps/A042CP6NUBE/interactive-messages?).
- Remember to configure SSO for the SSH key you're using on Workspace since this is an Anyscale private repo.
- When ready to deploy as an Anyscale Service, download the repo as a ZIP and store on S3 to reference in the YAML file.

# Deploy as Anyscale Service
Because Anyscale Service uses authentication bearer, Slack cannot directly query the endpoint. The workaround is to use CloudFront:
1. Create a new distribution
2. Set the _Origin_ to the endpoint URL and the _Origin path_ to `/`
3. Set _Allowed HTTP methods_ to "GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE"
4. Add a header key-value pair as: `Authorization`:`Bearer WpVq-xyz`
5. Use the _Distribution domain name_ as the _Request URL_ in Slack's _Interactivity & Shortcuts_ (plus the endpoint path e.g. `/ray/events`

[Here is the current CloudFront distribution](https://us-east-1.console.aws.amazon.com/cloudfront/v3/home?region=us-west-1#/distributions/E35RGC8ZRKLR8M)
