"""
Configuration settings for the Call Analysis application
"""

# Analysis thresholds and targets
QUALITY_SCORE_TARGET = 85.0
SENTIMENT_SCORE_TARGET = 4.0
MAX_NEGATIVE_SENTIMENT_RATIO = 0.3

# Scoring deductions
DEDUCTIONS = {
    'high_negative_sentiment': 20,
    'escalation_failure': 15,
    'lack_of_empathy': 10,
    'customer_frustration': 10,
    'excessive_duration': 5
}

# Keywords for analysis
KEYWORDS = {
    'escalation': ['escalate', 'supervisor', 'manager', 'complaint'],
    'empathy': ['understand', 'sorry', 'apologize', 'help'],
    'frustration': ['frustrated', 'angry', 'upset', 'annoyed'],
    'failure': ['procedure', 'failed', 'mistake', 'error']
}

# Quality score ranges
QUALITY_RANGES = {
    'excellent': (90, 100),
    'good': (80, 89),
    'average': (70, 79),
    'poor': (60, 69),
    'critical': (0, 59)
}

# Supported audio formats
SUPPORTED_FORMATS = ['mp3', 'wav', 'm4a', 'flac', 'webm']

# UI settings
UI_CONFIG = {
    'page_title': 'Critical Call Analysis',
    'page_icon': '📞',
    'layout': 'wide',
    'sidebar_width': 300
}

# AssemblyAI configuration
ASSEMBLYAI_CONFIG = {
    'sentiment_analysis': True,
    'auto_highlights': True,
    'iab_categories': True,
    'speaker_labels': True,
    'punctuate': True,
    'format_text': True,
    'language_detection': True
}