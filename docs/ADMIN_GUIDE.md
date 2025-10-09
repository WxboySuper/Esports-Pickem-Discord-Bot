# Admin Guide

This guide covers the admin-only commands for managing contests and match schedules in the Esports Pick'em Discord Bot.

## Prerequisites

To use admin commands, your Discord user ID must be added to the `ADMIN_IDS` environment variable. This is a comma-separated list of Discord user IDs.

Example `.env` configuration:
```
ADMIN_IDS=123456789,987654321
```

## Admin Commands

### `/create_contest` - Create a New Contest

Creates a new pick'em contest with a specified name and date range.

**Parameters:**
- `name` (string): Contest name (e.g., "VCT 2025 Spring Split")
- `start_date` (string): Start date in ISO 8601 format (e.g., "2025-01-15T00:00:00")
- `end_date` (string): End date in ISO 8601 format (e.g., "2025-03-31T23:59:59")

**Example:**
```
/create_contest name:"VCT 2025 Spring Split" start_date:"2025-01-15T00:00:00" end_date:"2025-03-31T23:59:59"
```

**Response:**
The bot will respond with an embed showing:
- Contest ID (used for uploading matches)
- Start Date
- End Date

**Notes:**
- End date must be after start date
- Dates can include timezone information (e.g., "2025-01-15T00:00:00Z" or "2025-01-15T00:00:00+00:00")
- The contest ID is needed for the `/upload_matches` command

### `/upload_matches` - Upload Match Schedule via CSV

Uploads a match schedule from a CSV file to an existing contest.

**Parameters:**
- `contest_id` (integer): The ID of the contest (obtained from `/create_contest`)
- `csv_file` (file): CSV file containing match schedule

**CSV Format:**

The CSV file must have the following columns:

| Column | Required | Description |
|--------|----------|-------------|
| `scheduled_time` | Yes | Match date/time in ISO 8601 format |
| `team1` | Yes | First team name |
| `team2` | Yes | Second team name |
| `external_id` | No | Optional external reference ID |

**CSV Example:**

See [sample_matches.csv](./sample_matches.csv) for a complete example.

```csv
scheduled_time,team1,team2,external_id
2025-01-15T14:00:00Z,Team Liquid,Cloud9,vlr-match-001
2025-01-15T16:30:00Z,Sentinels,100 Thieves,vlr-match-002
2025-01-16T14:00:00Z,LOUD,NRG Esports,vlr-match-003
```

**Example:**
```
/upload_matches contest_id:1 csv_file:[attach your CSV file]
```

**Response:**
The bot will:
1. Validate the CSV format and data
2. Report any validation errors with row numbers
3. Create match records in the database
4. Show summary of created/skipped matches

**Validation:**
- CSV must be UTF-8 encoded
- File size limit: 10 MB
- All required columns must be present
- `scheduled_time` must be in valid ISO 8601 format
- Empty fields will be rejected with specific error messages

**Error Handling:**
- If validation errors are found, NO matches will be imported
- Partial imports are supported: if some rows succeed and others fail during database insertion, successfully created matches remain in the database
- Errors are reported with specific row numbers and descriptions

## Workflows

### Creating a New Contest and Adding Matches

1. **Create the contest:**
   ```
   /create_contest name:"VCT Americas 2025" start_date:"2025-02-01T00:00:00Z" end_date:"2025-04-30T23:59:59Z"
   ```
   Note the Contest ID from the response (e.g., `5`)

2. **Prepare your CSV file:**
   - Create a CSV file with match data
   - Ensure proper ISO 8601 datetime format
   - Include team names exactly as they should appear

3. **Upload matches:**
   ```
   /upload_matches contest_id:5 csv_file:[your_matches.csv]
   ```

4. **Verify:**
   - Check the success message
   - Review any errors if matches were skipped
   - Users can now submit picks for the uploaded matches

## Tips

- **Date Formats:** Use ISO 8601 format with timezone (e.g., `2025-01-15T14:00:00Z` or `2025-01-15T14:00:00+00:00`)
- **Team Names:** Be consistent with team name formatting across your CSV
- **External IDs:** Use the `external_id` field to track matches from external APIs (e.g., VLR.gg)
- **Testing:** Test with a small CSV file first to ensure your format is correct
- **UTF-8 Encoding:** Ensure your CSV is saved as UTF-8, especially if using special characters

## Troubleshooting

### "You do not have permission to use this command"
- Your Discord user ID must be in the `ADMIN_IDS` environment variable
- Contact the bot administrator to add your ID

### "Contest with ID X not found"
- Verify you're using the correct contest ID from `/create_contest`
- Use `/list_contests` (if available) to see existing contests

### "Invalid datetime format"
- Use ISO 8601 format: `YYYY-MM-DDTHH:MM:SS` or `YYYY-MM-DDTHH:MM:SSZ`
- Example: `2025-01-15T14:00:00Z`

### "CSV missing required headers"
- Ensure your CSV has: `scheduled_time`, `team1`, `team2`
- Check for typos in header names
- Headers are case-sensitive

### "File must be a CSV file"
- File must have `.csv` extension
- Ensure you're attaching the correct file

## Security Notes

- Admin commands are restricted to users listed in `ADMIN_IDS`
- All admin actions are logged for audit purposes
- CSV files are validated before any database modifications
- Maximum file size is enforced to prevent abuse
