import time
import base64
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from openerp.osv import osv, fields
from openerp.tools.translate import _
from openerp.report import report_sxw

class work_time_analysis(osv.osv_memory):
    _name = "work.time.analysis"
    
    _columns = {
        'team_id': fields.many2one('account.analytic.account.team', string='Team'),
        'user_ids': fields.many2many('res.users',string="Users"),
        'date_start': fields.date('Start Date'),
        'date_stop': fields.date('End Date'),
    }

    _defaults = {
        'date_start': lambda *a: datetime.strftime(datetime.now().replace(day=1),'%Y-%m-%d'),
        'date_stop': lambda *a: datetime.strftime(datetime.now().replace(day=1)+relativedelta(months=1)-timedelta(days=1),'%Y-%m-%d'),
    }
    
    def _get_datas(self, cr, uid, ids, context=None):
        wiz_data = self.browse(cr, uid, ids[0], context=context)
        #contract object
        account_analytic_account_obj = self.pool.get('sale.subscription')
        project_issue_obj = self.pool.get('project.issue')
        #worklog object
        hr_analytic_timesheet_obj = self.pool.get('account.analytic.line')
        
        project_task_type_obj = self.pool.get('project.task.type')
        project_task_obj = self.pool.get('project.task')
        #result dictionary
        result_dict = {}
      
        
        #Stat: Team / Contracts / Working Time / Invoiceable Time
        
        result_dict['team-contract-time'] = {}
        contracts_dict = {}
        users = []
        user_step = 0
        number_users = len(wiz_data.user_ids)
        users_total = []
        for i in range((number_users*2)+2):
            users_total.append(0)
        for user in wiz_data.user_ids:
            users.append(user.name)
            
            hr_analytic_timesheet_ids = hr_analytic_timesheet_obj.search(cr, uid, [('user_id', '=', user.id),('date_begin','>=',wiz_data.date_start),('date_begin','<=',wiz_data.date_stop)])
            if hr_analytic_timesheet_ids:
                
                for worklog in hr_analytic_timesheet_obj.browse(cr, uid, hr_analytic_timesheet_ids):
                    account_id = {'id':-1,'name':'No Account',}
                    if worklog.account_id:
                        account_id = worklog.account_id
                    
                    if not contracts_dict.has_key(account_id.id):
                        values = []
                        for i in range((number_users*2)+2):
                            values.append(0)
                        contracts_dict[account_id.id] = {'name':worklog.account_id.name,'values':values,}
                    
                    invoicing_factor = 0
                    if worklog.to_invoice:
                        invoicing_factor = worklog.to_invoice.factor
                    
                    working_time = worklog.unit_amount
                    invoiceable_time = worklog.unit_amount*((100-invoicing_factor)/100)
                    contracts_dict[account_id.id]['values'][user_step] += working_time
                    contracts_dict[account_id.id]['values'][user_step+1] += invoiceable_time
                    contracts_dict[account_id.id]['values'][(number_users*2)] += working_time
                    contracts_dict[account_id.id]['values'][(number_users*2)+1] += invoiceable_time
                    users_total[user_step] += working_time
                    users_total[user_step+1] += invoiceable_time
                    users_total[(number_users*2)] += working_time
                    users_total[(number_users*2)+1] += invoiceable_time

            user_step += 2
        
        accounts = []
        for key, value in contracts_dict.iteritems():
            accounts.append(value)

        accounts = sorted(accounts, key=lambda k: k['name'])
            
        result_dict['team-contract-time'] = {'accounts':accounts, 'users': users,'users_total':users_total,}
            
        

        #Stat: Employee / Issues / SLA successful / SLA non-compliant
        result_dict['team-issue-sla-time'] = []
        for user in wiz_data.user_ids:
            contract_dict = {}
            
            project_task_type_obj = self.pool.get('project.task.type')
            project_task_type_unassigned = project_task_type_obj.search(cr, uid, [('name','=','Unassigned')])
            if project_task_type_unassigned:
                project_issue_ids = project_issue_obj.search(cr, uid, [('user_id', '=', user.id),('create_date','>=',wiz_data.date_start),('create_date','<=',wiz_data.date_stop),('stage_id','!=',project_task_type_unassigned[0])])
                if project_issue_ids:              
                    successful_issues = 0
                    for issue in project_issue_obj.browse(cr, uid, project_issue_ids):
                        date_open = datetime.strptime(issue.date_open, '%Y-%m-%d %H:%M:%S')
                        create_date = datetime.strptime(issue.create_date, '%Y-%m-%d %H:%M:%S')
                        date_diff_in_minutes = (date_open - create_date).total_seconds()/60                   
                        check = False
                        for rule in issue.analytic_account_id.first_subscription_id.contract_type.sla_id.sla_rule_ids:
                            if check:
                                break
                            if date_diff_in_minutes < rule.action_time:
                                successful_issues += 1
                                check = True
            
                    result_dict['team-issue-sla-time'].append({'name': user.name,'successful':successful_issues,'non_compliant':len(project_issue_ids)-successful_issues,'total':len(project_issue_ids),})
                
        result_dict['team-issue-sla-time'] = sorted(result_dict['team-issue-sla-time'], key=lambda k: k['name'])

        
        
        
        #Stat: Team / Issue / Time
        result_dict['team-issue-average-times'] = []
        for user in wiz_data.user_ids:
            contract_dict = {}
            project_issue_ids = project_issue_obj.search(cr, uid, [('user_id', '=', user.id),('create_date','>=',wiz_data.date_start),('create_date','<=',wiz_data.date_stop)])
            resolution_average = []
            reaction_average = []
            
            if project_issue_ids:
                first_issue = project_issue_obj.browse(cr, uid, project_issue_ids[0])
                max_resolution_time = 0
                min_resolution_time = 999999
                max_reaction_time = 0
                min_reaction_time = 999999
                
                for issue in project_issue_obj.browse(cr, uid, project_issue_ids):
                    
                    #Resolution Time
                    if issue.date_closed and len(issue.date_closed)>0:
                        date_closed = datetime.strptime(issue.date_closed, '%Y-%m-%d %H:%M:%S')
                        create_date = datetime.strptime(issue.create_date, '%Y-%m-%d %H:%M:%S')
                        resolution_diff = (date_closed - create_date).total_seconds()/60
                        if resolution_diff < 0:
                            resolution_diff = 0
                        if resolution_diff < min_resolution_time:
                            min_resolution_time = resolution_diff
                        if resolution_diff > max_resolution_time:
                            max_resolution_time = resolution_diff
                        resolution_average.append(resolution_diff)
                            
                    #Reaction Time
                    if issue.date_open and len(issue.date_open)>0:
                        date_open = datetime.strptime(issue.date_open, '%Y-%m-%d %H:%M:%S')
                        create_date = datetime.strptime(issue.create_date, '%Y-%m-%d %H:%M:%S')
                        reaction_diff = (date_open - create_date).total_seconds()/60
                        if reaction_diff < 0:
                            reaction_diff = 0
                        if reaction_diff < min_reaction_time:
                            min_reaction_time = reaction_diff
                        if reaction_diff > max_reaction_time:
                            max_reaction_time = reaction_diff
                        reaction_average.append(reaction_diff)
 
                reaction_average.sort()
                resolution_average.sort()
                average_reaction_time = reaction_average[0] if (len(reaction_average) == 1) else -1
                if (len(reaction_average) > 1):
                    average_reaction_time = reaction_average[int(len(reaction_average)/2)]
                average_resolution_time = resolution_average[0] if (len(resolution_average) == 1) else -1
                if (len(resolution_average) > 1):
                    average_resolution_time = resolution_average[int(len(resolution_average)/2)]
        
                result_dict['team-issue-average-times'].append({'name': user.name,
                                                                'average_reaction_time':average_reaction_time,
                                                                'min_reaction_time':min_reaction_time,
                                                                'max_reaction_time':max_reaction_time,
                                                                'average_resolution_time':average_resolution_time,
                                                                'min_resolution_time':min_resolution_time,
                                                                'max_resolution_time':max_resolution_time,
                                                                })
                
        result_dict['team-issue-average-times'] = sorted(result_dict['team-issue-average-times'], key=lambda k: k['name'])

        
        #Stat: Employee / Projects / Closed Tasks / Times
        
        result_dict['team-task-project-time'] = {}
        projects_dict = {}
        users = []
        user_step = 0
        number_users = len(wiz_data.user_ids)
        users_total = []
        for i in range((number_users*2)+2):
            users_total.append(0)
        
        project_task_type_closed_ids = project_task_type_obj.search(cr, uid, [('closed', '=', True)])
        
        for user in wiz_data.user_ids:
            users.append(user.name)
            
            project_task_ids = project_task_obj.search(cr, uid, [('user_id', '=', user.id),('stage_id', 'in', project_task_type_closed_ids),('create_date','>=',wiz_data.date_start),('create_date','<=',wiz_data.date_stop)])
            if project_task_ids:
                
                for task in project_task_obj.browse(cr, uid, project_task_ids):
                    project_id = {'id':-1,'name':'No Project',}
                    if task.project_id:
                        project_id['id'] = task.project_id
                    
                    if not projects_dict.has_key(project_id['id']):
                        values = []
                        for i in range((number_users*2)+2):
                            values.append(0)
                        projects_dict[project_id['id']] = {'name':task.project_id.name,'values':values,}
                    
                    planned_hours = task.planned_hours
                    working_hours = 0
                    
                    for worklog in task.timesheet_ids:
                        working_hours += worklog.unit_amount
                    
                    projects_dict[project_id.id]['values'][user_step] += planned_hours
                    projects_dict[project_id.id]['values'][user_step+1] += working_hours
                    projects_dict[project_id.id]['values'][(number_users*2)] += planned_hours
                    projects_dict[project_id.id]['values'][(number_users*2)+1] += working_hours
                    users_total[user_step] += planned_hours
                    users_total[user_step+1] += working_hours
                    users_total[(number_users*2)] += planned_hours
                    users_total[(number_users*2)+1] += working_hours

            user_step += 2
        
        projects = []
        for key, value in projects_dict.iteritems():
            projects.append(value)

        projects = sorted(projects, key=lambda k: k['name'])
            
        result_dict['team-task-project-time'] = {'projects':projects, 'users': users,'users_total':users_total,}
        
        
        return result_dict

    def get_report(self, cr, uid, ids, context=None):
        data = self._get_datas(cr, uid, ids, context=context)
                
        datas = {
             'ids': [],
             'model': 'work.time.analysis',
             'form': data,
        }
        return self.pool['report'].get_action(cr, uid, [], 'work_time_analysis_report.analysis_document', data=datas, context=context)

    
    def add_team_to_users(self, cr, uid, ids, context=None):
        record = self.browse(cr, uid, ids[0])
        if record.team_id:
            for user in  record.team_id.users:
                record.user_ids = [user.id]
        return {
        'context': context,
        'view_type': 'form',
        'view_mode': 'form',
        'res_model': 'work.time.analysis',
        'res_id': ids[0],
        'view_id': False,
        'type': 'ir.actions.act_window',
        'target': 'new',
        }
        
    def format_decimal_number(self, number, point_numbers=2, separator=','):
        number_string = str(round(round(number, point_numbers+1),point_numbers))
        for x in range(0, point_numbers):
            if len(number_string[number_string.rfind('.')+1:]) < 2:
                number_string += '0'
            else:
                break        
        return number_string.replace('.',separator)
        
    def decimal_to_hours(self, hoursDecimal):
        hours = int(hoursDecimal);
        minutesDecimal = ((hoursDecimal - hours) * 60);
        minutes = int(minutesDecimal);
        if minutes<10:
            minutes = "0"+str(minutes)
        else:
            minutes = str(minutes)
        hours = str(hours)
        return hours + ":" + minutes
        
class work_time_analysis_print(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(work_time_analysis_print, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
        })

class wrapped_work_time_analysis_print(osv.AbstractModel):
    _name = 'report.work_time_analysis_report.analysis_document'
    _inherit = 'report.abstract_report'
    _template = 'work_time_analysis_report.analysis_document'
    _wrapped_report_class = work_time_analysis_print
