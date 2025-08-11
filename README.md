# Critical Call Analysis Tool

A comprehensive customer service call analysis application using Streamlit and AssemblyAI that evaluates agent performance and provides detailed insights.

## Features

- **Audio Transcription**: Convert MP3/WAV files to text using AssemblyAI
- **Quality Scoring**: Automated agent performance evaluation
- **Sentiment Analysis**: Real-time sentiment tracking throughout the call
- **Issue Detection**: Identifies common customer service problems
- **Interactive Dashboard**: Clean, professional UI similar to call center analytics
- **JSON Export**: Download complete analysis results

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd speech_ai
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Get your AssemblyAI API key:
   - Sign up at [AssemblyAI](https://www.assemblyai.com/)
   - Get your free API key from the dashboard

## Usage

1. Run the Streamlit application:
```bash
streamlit run app.py
```

2. Open your web browser and go to `http://localhost:8501`

3. Enter your AssemblyAI API key in the sidebar

4. Upload an MP3 or WAV file of a customer service call

5. Wait for the analysis to complete (usually 2-5 minutes depending on file size)

6. Review the results in the dashboard:
   - **Call Overview**: Agent info, customer info, date/time, duration
   - **Performance Metrics**: Quality score, sentiment score, issues count
   - **Identified Issues**: Specific problems found in the call
   - **Call Transcript**: Full transcription with summary

7. Download the complete analysis as JSON

## Analysis Features

### Quality Score Calculation
- Base score of 85%
- Deductions for:
  - High negative sentiment (20 points)
  - Escalation procedure failures (15 points)
  - Lack of empathy (10 points)
  - Customer frustration (10 points)
  - Excessive call duration (5 points)

### Sentiment Analysis
- Real-time sentiment tracking throughout the call
- Overall sentiment score from 1-5
- Identifies positive, neutral, and negative segments

### Issue Detection
- Escalation procedure violations
- Lack of empathy indicators
- Customer frustration signals
- Call efficiency problems

## Supported Audio Formats

- MP3
- WAV
- M4A
- FLAC

## API Requirements

- AssemblyAI API key (free tier available)
- Internet connection for API calls

## Sample Output

The application generates a comprehensive JSON report including:

```json
{
  "call_overview": {
    "agent": {
      "name": "Alex Thompson",
      "type": "Human Agent"
    },
    "customer": {
      "name": "Sandra Miller", 
      "type": "Customer Support"
    },
    "date_time": {
      "date": "2024-01-15",
      "time": "16:45"
    },
    "duration": "8:23"
  },
  "performance_metrics": {
    "quality_score": {
      "score": "67%",
      "target": "85%",
      "variance": "-18.0% below target"
    },
    "sentiment_score": {
      "score": "2.1/5",
      "target": "4.0/5", 
      "status": "Below expected"
    },
    "issues_identified": {
      "count": 4,
      "type": "Critical Issues"
    }
  }
}
```

## Troubleshooting

### Common Issues

1. **API Key Error**: Make sure your AssemblyAI API key is valid and has available credits
2. **File Upload Error**: Ensure your audio file is in a supported format (MP3, WAV, M4A, FLAC)
3. **Transcription Failed**: Check your internet connection and API key permissions

### Performance Tips

- Smaller audio files (under 50MB) process faster
- Clear audio quality improves transcription accuracy
- Calls under 30 minutes provide more accurate analysis

## Development

### Project Structure
```
speech_ai/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

### Key Components

- `CallAnalyzer`: Main analysis class handling AssemblyAI integration
- `transcribe_audio()`: Handles audio transcription with sentiment analysis
- `calculate_quality_score()`: Evaluates agent performance
- `analyze_call()`: Main analysis pipeline

## License

MIT License - see LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review AssemblyAI documentation
3. Create an issue in this repository