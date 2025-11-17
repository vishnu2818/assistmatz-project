# from odoo import http


# class VinuCustomProject(http.Controller):
#     @http.route('/vinu_custom_project/vinu_custom_project', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/vinu_custom_project/vinu_custom_project/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('vinu_custom_project.listing', {
#             'root': '/vinu_custom_project/vinu_custom_project',
#             'objects': http.request.env['vinu_custom_project.vinu_custom_project'].search([]),
#         })

#     @http.route('/vinu_custom_project/vinu_custom_project/objects/<model("vinu_custom_project.vinu_custom_project"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('vinu_custom_project.object', {
#             'object': obj
#         })

