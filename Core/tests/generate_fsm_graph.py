"""
Creates a visual representation of the state machine with graphviz
"""
# pylint: skip-file

from graphviz import Digraph

from cc.synchronization.syncfsm import FSM_NODE_CONFIG


def generate_graph():
    """ generates the fsm graph """
    fms_config = FSM_NODE_CONFIG
    states = set()

    for event in fms_config['events']:
        if 'source' in event:
            if isinstance(event['src'], list):
                for state in event['src']:
                    states.add(state)
            else:
                states.add(event['src'])
        if event['dst'] != '=':
            states.add(event['dst'])

    graph = Digraph(format='svg')
    graph.body.extend(['rankdir=LR', 'size="5"'])

    graph.attr('node', shape='doublecircle')

    graph.node(fms_config['initial'])

    graph.attr('node', shape='circle')
    for state in states:
        label = ['<b>{}</b>'.format(state)]
        name = 'onenter{}'.format(state)
        if name in fms_config['callbacks']:
            label.append('<br/>{}()'.format(fms_config['callbacks'][name].__name__))

        graph.node(state, label='<{}>'.format("\n".join(label)))
    for event in fms_config['events']:
        if 'src' in event and event['src'] != '*':
            for eventprefix in ['onafter', 'on', 'onbefore']:
                eventname = '{}{}'.format(eventprefix, event['name'])
                if eventname in fms_config['callbacks']:
                    tail_label = '{}()'.format(
                        fms_config['callbacks'][eventname].__name__)
                    break
            else:
                tail_label = ''

            if event['dst'] == '=':
                graph.edge(event['src'], event['src'], label=event['name'],
                           taillabel=tail_label)
            else:
                graph.edge(event['src'], event['dst'], label=event['name'],
                           taillabel=tail_label)

    print(graph.source)

    graph.render()


if __name__ == "__main__":
    generate_graph()
