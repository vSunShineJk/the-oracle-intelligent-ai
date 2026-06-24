# Moodle API Manual

Base URL: read from env `MOODLE_URL`
Token: read from env `MOODLE_TOKEN`

All calls go to:
  GET {MOODLE_URL}/webservice/rest/server.php
  ?wstoken={MOODLE_TOKEN}&moodlewsrestformat=json&wsfunction={function}&{params}

## Functions

### core_course_get_courses
Returns all courses the user is enrolled in.
No required parameters.
Key response fields per course:
  id, fullname, shortname

### mod_assign_get_assignments
Returns all assignments for given course IDs.
Parameter: courseids[0]=<id>, courseids[1]=<id>, ...
Key response fields per assignment:
  id, name, duedate (unix timestamp), cutoffdate (unix timestamp), course (course id)

### mod_assign_get_submission_status
Returns submission status for one assignment.
Parameter: assignid=<id>
Key response fields:
  submission.status ("submitted" | "new"), submission.timemodified
  grading.grade (float or null), feedback.feedbackcomments.feedbacktext

### core_calendar_get_calendar_events
Returns upcoming calendar events (includes assignment deadlines).
Parameters: options[userevents]=1, options[siteevents]=1, timestart=<unix>, timeend=<unix>
Key response fields per event:
  id, name, timestart (unix), eventtype ("open" | "due" | "user"), modulename

### core_grades_get_grades
Returns grades for a course.
Parameters: courseid=<id>
Key response fields per item:
  itemname, grades[0].str_grade, grades[0].feedback

## Rules for Oracle
- Use mod_assign_get_assignments when the user asks about deadlines, upcoming assignments, or workload.
- Use mod_assign_get_submission_status when the user asks if they submitted something.
- Use core_grades_get_grades when the user asks about their grade in a course.
- Use core_calendar_get_calendar_events for a full schedule view.
- After every fetch, the tool automatically appends to moodle_state.md — no extra action needed.
- Read moodle_state.md first before deciding to re-fetch — only re-fetch if the data might be stale (older than ~1 hour or user explicitly asks to refresh).