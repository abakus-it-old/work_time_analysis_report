{
    'name': 'Work time analysis report',
    'version': '9.0.1.0',
    'category': 'Human Resources',
    'description': 
    """
    Work time analysis report.

    This modules adds a report, accessible by a wizard, that allows to print a timesheet report for teams on contracts.
    
    This module has been developed by Bernard Delhez, intern @ AbAKUS it-solutions.
    """,
    'depends': [
        'account_analytic_account_improvements',
        'hr_analytic_timesheet_improvements',
    ],
    'data': [
        'wizard/work_time_analysis_view.xml',
        'report/work_time_analysis_report.xml',
    ],
    'installable': True,
    'author': "Bernard DELHEZ, AbAKUS it-solutions SARL",
    'website': "http://www.abakusitsolutions.eu",
}
