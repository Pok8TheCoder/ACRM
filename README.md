# ACRM - Advanced Campus Resource Manager

A Flask-based web application for intelligent campus resource management and student success prediction.

## Features

- **Smart Timetable Management**: AI-powered scheduling eliminates conflicts and optimizes resources
- **AI-Powered Dropout Prediction**: Machine learning models identify at-risk students with 92% accuracy
- **Personalized Interventions**: Automated alerts and personalized recommendations for student support
- **Student Dashboard**: Real-time analytics and performance tracking
- **Intelligent Analytics**: Comprehensive insights into academic performance and engagement
- **Responsive Design**: Mobile-friendly interface built with Tailwind CSS

## Project Structure

```
ACRM/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/             # HTML templates
│   ├── base.html         # Base template with navbar and footer
│   ├── home.html         # Landing page
│   ├── features.html     # Features showcase
│   ├── dashboard.html    # Student dashboard
│   ├── demo.html         # Demo scheduling page
│   └── contact.html      # Contact form
├── static/                # Static files
│   ├── css/
│   │   └── style.css     # Custom styles
│   ├── js/
│   │   └── main.js       # JavaScript utilities
│   └── images/           # Images and assets
└── README.md
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python app.py
```

The application will start at `http://127.0.0.1:5000/`

### 3. Generate Rich Mock Data (optional)

Populate every admin tab (branches, semesters, subjects, students, resources, and faculty) with realistic demo data using the helper script:

```bash
# macOS/Linux
PYTHONPATH=. python generate_mock_data.py --reset

# Windows PowerShell
$env:PYTHONPATH="$(Get-Location)"; python generate_mock_data.py --reset
```

Flags you can tweak:

- `--institution`: target institution folder (default: `iit_delhi`)
- `--students-per-class`: defaults to 10 (48 classes → 480 students)
- `--class-capacity` / `--lab-capacity`: enforce 10-seat classrooms and 5-seat labs by default
- `--reset`: wipes the institution folder before seeding so you start fresh

The script creates:

- 4 branches × 6 semesters with A/B sections (48 classes total)
- 5 subjects per semester (first-semester subjects shared across branches)
- 10 students per class with realistic IDs/emails
- Campus layout with 4 floors, 24 sections, 48 classrooms (capacity 10) and 24 labs (capacity 5)
- 30 rotating faculty assignments covering every subject/class combination

### 4. Available Routes

- `/` - Home page (hero section and features)
- `/features` - Detailed features showcase
- `/dashboard` - Student success dashboard with analytics
- `/demo` - Schedule a demo form
- `/contact` - Contact us form

## API Endpoints

### Demo Request
- **POST** `/api/demo-request`
- Submits a demo request with name, email, institution, role, and selected time

### Contact Message
- **POST** `/api/contact-message`
- Submits a contact form message

## Technology Stack

- **Backend**: Flask 2.3.3
- **Frontend**: HTML5, Tailwind CSS, JavaScript
- **Charts**: Chart.js for data visualization
- **Icons**: Font Awesome 6.4.0, Lucide Icons
- **UI Framework**: Tailwind CSS with custom theme colors

## Color Scheme

- Primary Navy: `#001F3F`
- Accent Orange: `#FF6B35`
- Light Navy: `#003D5C`
- Dark Navy: `#000A14`
- White: `#FFFFFF`

## Features by Page

### Home (/)
- Hero section with Hyperspeed-inspired background
- Problem statement and key benefits
- Feature highlights
- Call-to-action sections
- Animated scroll indicators

### Features (/features)
- Interactive feature selector
- Detailed feature benefits
- Impact metrics and statistics
- Additional capabilities grid
- Feature comparison

### Dashboard (/dashboard)
- KPI cards (GPA, Attendance, Performance, Support)
- Performance analytics with charts
  - Attendance trends
  - Subject performance comparison
  - Engagement distribution
  - Risk assessment
- AI-powered recommendations
- Personalized action items

### Demo (/demo)
- Demo booking form
- Time slot selection
- Demo inclusions checklist
- Testimonials from existing clients
- Form validation and submission

### Contact (/contact)
- Contact information cards
- Contact form with validation
- Business hours
- FAQ section with expandable items
- Multiple contact methods (email, phone, address)

## Development

### Enable Debug Mode
The app runs in debug mode by default. To disable:

```python
app.run(debug=False)
```

### Modify Templates
All HTML templates are in the `templates/` folder and use Jinja2 templating. The `base.html` provides the base structure inherited by all pages.

### Add New Pages
1. Create a new template in `templates/`
2. Add a route in `app.py`
3. Link from navigation in `base.html`

### Add Styling
Edit `static/css/style.css` for custom styles, or add inline Tailwind classes to templates.

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

## Performance Optimizations

- Lazy loading for images
- CSS animations for smooth transitions
- Responsive grid layouts
- Optimized chart rendering
- Debounced scroll events

## Security Considerations

- CORS enabled for API endpoints
- Form validation on client and server side
- XSS protection through Jinja2 escaping
- CSRF protection ready (can be added with Flask-WTF)

## Future Enhancements

- Database integration for form submissions
- Email notifications for demo requests
- User authentication system
- Student profile dashboards
- Real-time data integration
- Advanced AI recommendations engine
- Mobile app version
- API authentication and rate limiting

## License

© 2025 ACRM - Advanced Campus Resource Manager. All rights reserved.

## Support

For questions or support, contact: info@acrm.edu
Phone: +1 (555) 123-4567
