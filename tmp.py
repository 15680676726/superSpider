import inspect
from copaw.industry import IndustryService
print(IndustryService.get_instance_detail.__qualname__)
print(inspect.getsource(IndustryService.get_instance_detail))
